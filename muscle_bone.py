import math
import maya.cmds as cmds
import maya.api.OpenMaya as om


class MuscleJointGroup:

    def __init__(
        self,
        muscleName="Muscle",
        muscleLength=5.0,
        compressionFactor=0.7,
        stretchFactor=1.3,
        compressionOffset=None,
        stretchOffset=None
    ):
        self.muscleName = muscleName
        self.muscleLength = muscleLength
        self.compressionFactor = compressionFactor
        self.stretchFactor = stretchFactor
        self.stretchOffset = stretchOffset or [0.0, 0.0, 0.0]
        self.compressionOffset = compressionOffset or [0.0, 0.0, 0.0]

        self.muscleOrigin = None
        self.muscleInsertion = None
        self.muscleBase = None
        self.muscleTip = None
        self.muscleDriver = None
        self.muscleOffset = None
        self.muscleJoint = None

        self.mainAimConstraint = None
        self.mainPointConstraint = None

        # edit mode
        self.originLoc = None
        self.insertionLoc = None
        self.driverLoc = None

        # creation
        self.create()
        self._addSDK()


    @staticmethod
    def createJoint(jointName, parent=None, radius=1.0):
        joint = cmds.createNode("joint", name=jointName)
        cmds.setAttr("{}.radius".format(joint), radius)

        if parent:
            joint = cmds.parent(joint, parent, relative=True)[0]
            cmds.setAttr("{}.translate".format(joint), 0, 0, 0)
            cmds.setAttr("{}.rotate".format(joint), 0, 0, 0)
            cmds.setAttr("{}.jointOrient".format(joint), 0, 0, 0)

        return joint

    # ======================================================
    # MODULE 1: CREATE MUSCLE JOINT SYSTEM
    # ======================================================

    def create(self):

        # 1. Create muscle endpoints
        self.muscleOrigin = self.createJoint("{}_muscleOrigin".format(self.muscleName))

        self.muscleInsertion = self.createJoint("{}_muscleInsertion".format(self.muscleName))

        cmds.setAttr("{}.translateX".format(self.muscleInsertion), self.muscleLength)

        # Initialize origin orientation
        tempAim = cmds.aimConstraint(self.muscleInsertion, self.muscleOrigin, aimVector=(1, 0, 0), upVector=(0, 1, 0), worldUpType="scene")
        cmds.delete(tempAim)

        # 2. Create muscle base
        self.muscleBase = self.createJoint(
            "{}_muscleBase".format(self.muscleName),
            parent=self.muscleOrigin,
            radius=0.5
        )

        cmds.pointConstraint(self.muscleOrigin, self.muscleBase,maintainOffset=False)

        # Base X-axis aims toward insertion
        self.mainAimConstraint = cmds.aimConstraint(self.muscleInsertion, self.muscleBase, aimVector=(1, 0, 0),upVector=(0, 1, 0),
                                                    worldUpType="objectrotation",worldUpObject=self.muscleOrigin, worldUpVector=(0, 1, 0))

        # 3. Create muscle tip
        self.muscleTip = self.createJoint("{}_muscleTip".format(self.muscleName),parent=self.muscleBase,radius=0.5)

        # Tip follows insertion.
        # Tip.translateX measures muscle length.
        cmds.pointConstraint(self.muscleInsertion,self.muscleTip, maintainOffset=False)

        # 4. Create midpoint driver
        self.muscleDriver = self.createJoint( "{}_muscleDriver".format(self.muscleName), parent=self.muscleBase, radius=0.5)

        self.mainPointConstraint = cmds.pointConstraint( self.muscleBase, self.muscleTip, self.muscleDriver, maintainOffset=False)

        # 5. Create deformation joints
        self.muscleOffset = self.createJoint( "{}_muscleOffset".format(self.muscleName), parent=self.muscleDriver, radius=0.75)

        self.muscleJoint = self.createJoint(
            "{}_JOmuscle".format(self.muscleName),
            parent=self.muscleOffset,
            radius=1.0
        )

    # ======================================================
    # MODULE 2: CREATE EDIT FOR OFFSET POS SETUP
    # ======================================================
    def edit(self):

        # this is a helper fuc ( we want to scale it bigger
        def createSpaceLocator(scaleValue, **kwargs):
            loc = cmds.spaceLocator(**kwargs)[0]
            for axis in "XYZ":
                cmds.setAttr(f"{loc}.localScale{axis}", scaleValue)
            return loc

        cmds.setAttr(f"{self.muscleOrigin}.overrideEnabled", True)
        cmds.setAttr(f"{self.muscleOrigin}.overrideDisplayType", 1)
        # this means set it tobe template mode so that cannot be chosen
        cmds.setAttr(f"{self.muscleInsertion}.overrideEnabled", True)
        cmds.setAttr(f"{self.muscleInsertion}.overrideDisplayType", 1)

        self.originLoc = createSpaceLocator(3, name = f"{self.muscleName}_muscleOrigin_loc")
        cmds.matchTransform(self.originLoc, self.muscleOrigin, position = True, rotation = False, scale = False)
        cmds.pointConstraint(self.originLoc, self.muscleOrigin, maintainOffset=False, weight = 1)

        self.insertionLoc =createSpaceLocator(3, name = f"{self.muscleName}_muscleInsertion_loc")
        cmds.matchTransform(self.insertionLoc, self.muscleInsertion, position=True, rotation=False, scale=False)
        cmds.pointConstraint(self.insertionLoc, self.muscleInsertion, maintainOffset=False, weight=1)

        # use X axis as the aim axis to have them look at each other
        # what we do is to aim constraint them to each other
        # cmds.aim
        cmds.aimConstraint(self.insertionLoc, self.originLoc, aimVector=(-1, 0, 0), upVector=(0, 1, 0),
                           worldUpType="scene", weight =1)
        cmds.aimConstraint(self.originLoc, self.insertionLoc,  aimVector=(1, 0, 0), upVector=(0, 1, 0),
                           worldUpType="scene", weight=1)


    def update(self):
        pass

    def delete(self):
        pass


    # ======================================================
    # MODULE 3: SET DRIVEN KEYS
    # ======================================================

    def _addSDK(self):

        # Muscle length is measured along local X
        driverAttr = "{}.translateX".format(self.muscleTip)

        restLength = cmds.getAttr(driverAttr)

        if restLength <= 0:
            raise ValueError("Muscle rest length must be positive.")

        if not (0 < self.compressionFactor <= 1 and self.stretchFactor >= 1):
            raise ValueError(
                "Expected 0  compressionFactor <= 1 "
                "and stretchFactor >= 1."
            )

        def setSDKState(lengthRatio, offset):

            currentLength = restLength * lengthRatio

            # Volume preservation:
            # scaleX = lengthRatio
            # scaleY = scaleZ = sqrt(1 / lengthRatio)
            crossSectionScale = math.sqrt(
                1.0 / lengthRatio
            )

            for index, axis in enumerate("XYZ"):

                scaleAttr = "{}.scale{}".format(
                    self.muscleJoint, axis
                )

                translateAttr = "{}.translate{}".format(
                    self.muscleJoint, axis
                )

                if axis == "X":
                    scaleValue = lengthRatio
                else:
                    scaleValue = crossSectionScale

                cmds.setDrivenKeyframe(
                    scaleAttr,
                    currentDriver=driverAttr,
                    driverValue=currentLength,
                    value=scaleValue,
                    inTangentType="linear",
                    outTangentType="linear"
                )

                cmds.setDrivenKeyframe(
                    translateAttr,
                    currentDriver=driverAttr,
                    driverValue=currentLength,
                    value=offset[index],
                    inTangentType="linear",
                    outTangentType="linear"
                )

        # 1. Compression state
        setSDKState(self.compressionFactor, self.compressionOffset)

        # 2. Rest state
        setSDKState(1.0,[0.0, 0.0, 0.0])

        # 3. Stretch state
        setSDKState(self.stretchFactor,self.stretchOffset)

    @classmethod
    def createFromAttachObjs(cls,
                             muscleName,
                             originAttachObj,
                             insertionAttachObj,
                             compressionFactor = 0.7,
                             stretchFactor = 1.3,
                             compressionOffset = None,
                             stretchOffset = None):

        originAttachPos = om.MVector(cmds.xform(originAttachObj, translation = True, worldSpace = True, query = True))
        insertionAttachPos = om.MVector(cmds.xform(insertionAttachObj, translation = True, worldSpace = True, query = True))
        muscleLength = (originAttachPos - insertionAttachPos).length()

        MuscleJointGroup = cls(muscleName, muscleLength, compressionFactor, stretchFactor, compressionOffset, stretchOffset)
        # here obj = cls(...) equals obj = MuscleJointGroup(...)

        ## here need to match pos

        cmds.parent(MuscleJointGroup.muscleOrigin, originAttachObj)
        cmds.parent(MuscleJointGroup.muscleInsertion, insertionAttachObj)

        return muscleJointGroup

# ==========================================================
# TEST
# ==========================================================
