from numpy import arange
from narrow_convex_hull import getSurfaceExtremumPoints, removeDuplicates, normal
from pinocchio import XYZQUATToSE3
from numpy import array
from sl1m.problem_definition import LF, RF

MAX_SURFACE = 0.1 # about fourth the size of the foot area 
ROBOT_NAME = 'talos'


def area(s):
    a = 0
    for i in range(len(s)-1):
      a += (s[i][0]*s[i+1][1])-(s[i][1]*s[i+1][0])
    return abs(a * 0.5)

def listToArray (seqs):
    nseq = []; nseqs= []
    for seq in seqs:
        if seq == []:
            nseqs.append(nseq)
        else:
            nseq = []
            for surface in seq:
                if surface != []:
                    nseq.append(array(surface).T)
            nseqs.append(nseq)
    return nseqs

def getRotationsFromConfigs(configs):
    R = []
    for config in configs:
        q_rot = config[3:7]
        R.append(XYZQUATToSE3([0,0,0]+q_rot).rotation)
    return R    

def getContactsNames(rbprmBuilder,i,q):
    if i % 2 == LF : # left leg 
        step_contacts = rbprmBuilder.clientRbprm.rbprm.getCollidingObstacleAtConfig(q, ROBOT_NAME + '_lleg_rom') 
    elif i % 2 == RF : # right leg
        step_contacts = rbprmBuilder.clientRbprm.rbprm.getCollidingObstacleAtConfig(q,ROBOT_NAME + '_rleg_rom')
    return step_contacts

def getContactsIntersections(rbprmBuilder,i,q):
      if i % 2 == LF : # left leg
          intersections = rbprmBuilder.getContactSurfacesAtConfig(q,ROBOT_NAME + '_lleg_rom')  
      elif i % 2 == RF : # right leg
          intersections = rbprmBuilder.getContactSurfacesAtConfig(q,ROBOT_NAME + '_rleg_rom')
      return intersections

# get all the contact surfaces (pts and normal)
def getAllSurfaces(afftool) :
    l = afftool.getAffordancePoints("Support")
    return [(getSurfaceExtremumPoints(el), normal(el[0])) for el in l]
    
# get surface information
def getAllSurfacesDict (afftool) :
    all_surfaces = getAllSurfaces(afftool) 
    all_names = afftool.getAffRefObstacles("Support") # id in names and surfaces match
    surfaces_dict = dict(zip(all_names, all_surfaces)) # map surface names to surface points
    return surfaces_dict

def getSurfacesFromGuideContinuous(rbprmBuilder,ps,afftool,viewer = None,step = 1.,useIntersection= False, pathId=None):
    if viewer : 
        from tools.display_tools import displaySurfaceFromPoints  # tool from hpp-rbprm
    
    window_size = 0.5 # smaller step at which we check the colliding surfaces
    if pathId == None:
        pathId = ps.numberPaths() -1
    pathLength = ps.pathLength(pathId) #length of the path
    
    # get surface information
    surfaces_dict = getAllSurfacesDict(afftool) # map surface names to surface points
    seqs = [] # list of list of surfaces : for each phase contain a list of surfaces. One phase is defined by moving of 'step' along the path
    t = 0.
    current_phase_end = step
    end = False
    i = 0

    while not end: # for all the path
        phase_contacts = []
        phase_contacts_names = []
        while t < current_phase_end: # get the names of all the surfaces that the rom collide while moving from current_phase_end-step to current_phase_end
            q = ps.configAtParam(pathId, t)
            step_contacts = getContactsIntersections(rbprmBuilder,i,q)
            step_contacts_names = getContactsNames(rbprmBuilder,i,q)
            # do not consider the duplicates yet
            phase_contacts += step_contacts
            phase_contacts_names += step_contacts_names
            t += window_size
            assert len(phase_contacts) == len(phase_contacts_names)
        # end current phase
        
        seq = []

        for i,contact in enumerate(phase_contacts):
            if contact != []:
                if viewer:
                    displaySurfaceFromPoints(viewer,contact,[0,0,1,1])
                if useIntersection and area(contact) > MAX_SURFACE:
                    seq.append(contact)
                else:
                    surface = surfaces_dict[phase_contacts_names[i]][0]
                    if surface not in seq: # check if there is duplicate
                        seq.append(surface)
                    sorted(seq)
        seqs.append(seq)

        # increase value for the next phase
        t = current_phase_end
        current_phase_end += step
        i += 0 # phase number

        if t == pathLength:
            current_phase_end = pathLength+0.01
        if t > pathLength:
            end = True
    # end of all guide path

    #get rotation matrix of the root at each step
    seqs = listToArray(seqs)
    configs = []
    for t in arange (0, pathLength, step) :
        configs.append(ps.configAtParam(pathId, t)) 
    R = getRotationsFromConfigs(configs)

    return R,seqs


def getSurfacesFromGuide(rbprmBuilder,ps,afftool,viewer = None,step = 1.,useIntersection = False, pathId = None):
    if viewer : 
        from tools.display_tools import displaySurfaceFromPoints  # tool from hpp-rbprm

    if pathId == None:
        pathId = ps.numberPaths() -1
    pathLength = ps.pathLength(pathId) #length of the path
    configs = []
    # get configuration along the path
    for s in arange (0, pathLength, step) :
        configs.append(ps.configAtParam(pathId, s)) 

    # get surface information
    surfaces_dict = getAllSurfacesDict(afftool)
    
    # get surface candidate at each discretization step
    # suppose that we start with the left leg
    seqs = []
    for i, q in enumerate(configs):    
        seq = [] 
        contacts = getContactsIntersections (rbprmBuilder,i,q)
        contact_names = getContactsNames (rbprmBuilder,i,q)
        assert len(contacts) == len(contact_names)

        for j, contact in enumerate(contacts):
            if contact != []:
                if viewer:
                    displaySurfaceFromPoints(viewer,contact,[0,0,1,1])
                if useIntersection and area(contact) > MAX_SURFACE:
                    seq.append(contact) 
                else:
                    seq.append(surfaces_dict[contact_names[j]][0])

        seqs.append(seq)
    
    # remove duplicates          
    for i, seq in enumerate(seqs): seqs[i] = removeDuplicates(seq)
    
    seqs = listToArray(seqs) # change the format from list to array
    R = getRotationsFromConfigs(configs)
    return R,seqs
    

    
# ONLY FOR EXPERIMENTS
def getSurfacesAll(ps,afftool,step_num):
    all_surfaces = sorted(getAllSurfaces(afftool))
    phase = [surf[0] for surf in all_surfaces]
    init = ps.getInitialConfig()

    seqs = []; R =[]
    for i in range(step_num):
        seqs.append(phase)
        R.append(XYZQUATToSE3([0,0,0]+init[3:7]).rotation)

    if (len(seqs[0])!= 1):
        seqs[0]=[seqs[0][0]]; seqs[-1]=[seqs[-1][-1]]
    seqs = listToArray(seqs) 

    return R,seqs

# contacts = getContactsIntersections (rbprmBuilder,i,q)
# contact_names = getContactsNames (rbprmBuilder,i,q)
# contact_surfaces = [surface_dict[contact_name][0] for contact_name in contact_names]
# contact_surfaces_ = [[array(contact_surface).T] for contact_surface in contact_surfaces]
# contacts_ = [[contact] for contact in surfaces[9]]

# draw_scene(contacts_)
# draw_scene(contact_surfaces_)
