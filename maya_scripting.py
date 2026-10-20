import maya.cmds as cmds
import maya.api.OpenMaya as om

def setup_twist_joint_chain(startJoint, endJoint = None, twistJointCount = 3,
                         twistAxis = (1, 0, 0),
                         upAxis = (0, 0, 1)):
    startJointName = startJoint[2:] if startJoint.startswith("JO") else startJoint

    if not endJoint:
        childrenJoints = cmds.listRelatives(startJoint, parent = False, children = True, type = "joint")
        if childrenJoints:
            endJoint = childrenJoints[0]

    if not cmds.ls(endJoint):
        raise Exception(f"Cannot find a valid joint chain starting with {startJoint}")

    # create twist joints
    twistjoints = []

    for index in range(twistJointCount):
        cmds.select(startJoint)
        # get rid of the prefix JO
        twistjointName = startJointName + f"Twist{index}"
        twistJoint = cmds.joint(name = twistjointName)
        twistjoints.append(twistJoint)

    # two point subtract is a vector
    jointChainLength = (om.MPoint(cmds.xform(endJoint, translation = True, worldSpace = True, query = True)) -
    om.MPoint(cmds.xform(startJoint, translation = True, worldSpace = True, query = True))).length()

    offsetRatio = 0.02
    jointChainLength*= 1-offsetRatio
    distributionDistance = jointChainLength / (len(twistjoints))
    for index, twistJoint in enumerate(twistjoints):
        # 在主轴上延申
        translation = distributionDistance * om.MVector(twistAxis)* (index +1)
        cmds.setAttr(f"{twistJoint}.translate", *translation)
        cmds.setAttr(f"{twistJoint}.radius", 2.0)

    cmds.select(startJoint)
    # 生成twistBasisJoint1
    twistBasisJoint1  = cmds.joint(name = startJointName + f"TwistBasis1")
    cmds.matchTransform(twistBasisJoint1, startJoint)
    cmds.setAttr(f"{twistBasisJoint1}.radius", 0.5)

    cmds.select(twistBasisJoint1)
    twistValueJoint = cmds.joint(name = startJointName + f"twistValue1")
    cmds.aimConstraint(endJoint, twistValueJoint, aimVector = twistAxis, upVector = upAxis ,
                       worldUpType = "objectrotation", worldUpObject = endJoint,
                       worldUpVector = upAxis, maintainOffset = True)
    

