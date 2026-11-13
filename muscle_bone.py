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

        # this is used to record the loc we created in edit mode
        self.tmpPointConstraintEdit = []

        # creation
        self.create()
        self.edit()  # enter edit mode at first
        #self._addSDK()


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

        self.tmpPointConstraintEdit.append(
            cmds.pointConstraint(self.originLoc, self.muscleOrigin, maintainOffset=False, weight = 1)[0])

        self.insertionLoc =createSpaceLocator(3, name = f"{self.muscleName}_muscleInsertion_loc")
        cmds.matchTransform(self.insertionLoc, self.muscleInsertion, position=True, rotation=False, scale=False)

        self.tmpPointConstraintEdit.append(
            cmds.pointConstraint(self.insertionLoc, self.muscleInsertion, maintainOffset=False, weight=1)[0])

        # use X axis as the aim axis to have them look at each other
        # what we do is to aim constraint them to each other
        # cmds.aim
        cmds.aimConstraint(self.insertionLoc, self.originLoc, aimVector=(-1, 0, 0), upVector=(0, 1, 0),
                           worldUpType="scene", weight =1)
        cmds.aimConstraint(self.originLoc, self.insertionLoc,  aimVector=(1, 0, 0), upVector=(0, 1, 0),
                           worldUpType="scene", weight=1)
        driverGrp = cmds.group(name = f"{self.muscleName}_muscleDriver_grp", empty = True)
        self.driverLoc = createSpaceLocator(2, name = f"{self.muscleName}_muscleDriver_loc")
        cmds.parent(self.driverLoc, driverGrp)

        # Older units may store the edited position on muscleOffset.
        cmds.matchTransform(driverGrp, self.muscleOffset, position = True, rotation = True, scale = False)
        cmds.parent(driverGrp, self.originLoc)

        # collect the point constraints so that we can delete them in apply mode together
        self.tmpPointConstraintEdit.append(
            cmds.pointConstraint(self.originLoc, self.insertionLoc, driverGrp, maintainOffset=True, weight = 1)[0])
        # the loc hierarchy is similar to the bone unit one , we also need the diver grp to be controlled & driver loc to control driver bone

        # here delete the originally point constraint
        cmds.delete(self.mainPointConstraint)
        self.mainPointConstraint = None
        cmds.setAttr(f"{self.muscleOffset}.translate", 0, 0, 0)
        self.tmpPointConstraintEdit.append(
            cmds.pointConstraint(self.driverLoc, self.muscleDriver, maintainOffset = False, weight = 1)[0])


    def update(self):
        """
        it is used to apply the changes we made in edit mode
        :return:
        """
        # Preserve the position selected with the driver locator.
        driverWorldPosition = cmds.xform(
            self.muscleDriver,
            query=True,
            worldSpace=True,
            translation=True
        )

        # remove point constraints
        # 如果delete [] 空list 会报错
        if self.tmpPointConstraintEdit:
            cmds.delete(self.tmpPointConstraintEdit)
            self.tmpPointConstraintEdit = []

        #cmds.delete(self.originLoc, self.insertionLoc, self.driverLoc)
        # use cmds.ls to filter out the "None"
        cmds.delete(cmds.ls([self.originLoc, self.insertionLoc, self.driverLoc]))

        # exist edit mode
        cmds.setAttr(f"{self.muscleOrigin}.overrideEnabled", False)
        cmds.setAttr(f"{self.muscleOrigin}.overrideDisplayType", 0)
        # this means set it to exit template mode so that can be chosen
        cmds.setAttr(f"{self.muscleInsertion}.overrideEnabled", False)
        cmds.setAttr(f"{self.muscleInsertion}.overrideDisplayType", 0)

        cmds.delete(self.mainAimConstraint)

        cmds.delete(cmds.aimConstraint(self.muscleInsertion, self.muscleOrigin, aimVector=(1, 0, 0), upVector=(0, 1, 0),
                           worldUpType="scene", weight =1, maintainOffset = False)) # 对齐 所以是false

        # use X as the main axis 重构 logic like in create mode
        self.mainAimConstraint = cmds.aimConstraint(self.muscleInsertion, self.muscleBase, aimVector=(1, 0, 0),
                                                    upVector=(0, 1, 0),
                                                    worldUpType="objectrotation", worldUpObject=self.muscleOrigin,
                                                    worldUpVector=(0, 1, 0))

        # Restore the edited position after the base is reoriented, and keep
        # its offset from the midpoint when the endpoints move.
        cmds.xform(self.muscleDriver, worldSpace=True, translation=driverWorldPosition)
        cmds.setAttr(f"{self.muscleOffset}.translate", 0, 0, 0)
        self.mainPointConstraint = cmds.pointConstraint(
            self.muscleBase,
            self.muscleTip,
            self.muscleDriver,
            maintainOffset=True,
            weight=1
        )

        # here since we change the original bone length, we want to reset the original length
        connections = cmds.listConnections(self.muscleJoint, source=True, destination=False) or []
        animCurveNodes = cmds.ls(connections, type=('animCurveUU', 'animCurveUL')) if connections else []
        if animCurveNodes:
            cmds.delete(animCurveNodes)
        self._addSDK()


    def delete(self):
        try:
            # if in edit mode, turn to update mode
            self.update()
        except RuntimeError as e:
            print(type(e).__name__, e)

        cmds.delete([self.muscleOrigin, self.muscleInsertion])




    # ======================================================
    # MODULE 3: SET DRIVEN KEYS
    # ======================================================

    def _addSDK(self):

        # Muscle length is measured along local X
        driverAttr = "{}.translateX".format(self.muscleTip)

        restLength = cmds.getAttr(driverAttr)

        if restLength <= 0:
            raise ValueError("Muscle rest length must be positive.")

        if not (0 < self.compressionFactor < 1 and self.stretchFactor > 1):
            raise ValueError(
                "Expected 0 < compressionFactor < 1 "
                "and stretchFactor > 1."
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
        cmds.matchTransform(
            MuscleJointGroup.originLoc,
            originAttachObj,
            position=True,
            rotation=False,
            scale=False
        )
        cmds.matchTransform(
            MuscleJointGroup.insertionLoc,
            insertionAttachObj,
            position=True,
            rotation=False,
            scale=False
        )

        cmds.parent(MuscleJointGroup.muscleOrigin, originAttachObj)
        cmds.parent(MuscleJointGroup.muscleInsertion, insertionAttachObj)
        cmds.parent(MuscleJointGroup.originLoc, originAttachObj)
        cmds.parent(MuscleJointGroup.insertionLoc, insertionAttachObj)

        return MuscleJointGroup


    def mirror(self, newMuscleName, originAttachObj, insertionAttachObj):

        originPos = om.MVector(cmds.xform(self.muscleOrigin, translation = True, worldSpace = True, query = True))
        insertionPos = om.MVector(cmds.xform(self.muscleInsertion, translation = True, worldSpace = True, query = True))
        driverPos = om.MVector(cmds.xform(self.muscleDriver, translation = True, worldSpace = True, query = True))

        # x axis is the mirror axis
        mirrorOriginPos = om.MVector(-originPos.x, originPos.y, originPos.z)
        mirrorInsertionPos = om.MVector(-insertionPos.x, insertionPos.y, insertionPos.z)
        mirrorDriverPos = om.MVector(-driverPos.x, driverPos.y, driverPos.z)

        # 另一侧的length
        muscleLength = om.MVector(insertionPos - originPos).length()
        mirrorMuscleJointGroup = MuscleJointGroup(
            newMuscleName, muscleLength,
            compressionFactor=self.compressionFactor,
            stretchFactor=self.stretchFactor,
            compressionOffset=self.compressionOffset,
            stretchOffset=self.stretchOffset
        )

        # match the edit locator to the pos
        cmds.xform(mirrorMuscleJointGroup.originLoc, translation = mirrorOriginPos, worldSpace = True)
        cmds.xform(mirrorMuscleJointGroup.insertionLoc, translation = mirrorInsertionPos, worldSpace=True)
        cmds.xform(mirrorMuscleJointGroup.driverLoc, translation = mirrorDriverPos, worldSpace=True)
        cmds.parent(mirrorMuscleJointGroup.muscleInsertion, insertionAttachObj)
        cmds.parent(mirrorMuscleJointGroup.muscleOrigin, originAttachObj)

        return mirrorMuscleJointGroup

    @classmethod
    def mirror2(cls, sourceMuscleName, newMuscleName, originAttachObj,
                insertionAttachObj, compressionFactor=0.7, stretchFactor=1.3,
                compressionOffset=None, stretchOffset=None):
        """Mirror existing scene joints across world X=0 into a new edit unit."""
        def resolve_node(name):
            matches = [node for node in (cmds.ls(name, long=True) or [])
                       if cmds.objectType(node, isAType="transform")]
            if len(matches) != 1:
                raise ValueError("Expected one scene transform for {!r}; found {}.".format(name, len(matches)))
            return matches[0]

        origin = resolve_node(sourceMuscleName + "_muscleOrigin")
        insertion = resolve_node(sourceMuscleName + "_muscleInsertion")
        driver = resolve_node(sourceMuscleName + "_muscleDriver")
        originAttachObj = resolve_node(originAttachObj)
        insertionAttachObj = resolve_node(insertionAttachObj)

        if not (0 < compressionFactor < 1 and stretchFactor > 1):
            raise ValueError("Expected 0 < compressionFactor < 1 and stretchFactor > 1.")
        for offset in (compressionOffset, stretchOffset):
            if offset is not None and len(offset) != 3:
                raise ValueError("Offsets must have three components.")
        for suffix in ("_muscleOrigin", "_muscleInsertion", "_muscleBase",
                       "_muscleTip", "_muscleDriver", "_muscleOffset", "_JOmuscle"):
            if cmds.ls(newMuscleName + suffix):
                raise ValueError("A node named {} already exists.".format(newMuscleName + suffix))

        originPos = om.MVector(cmds.xform(origin, query=True, worldSpace=True, translation=True))
        insertionPos = om.MVector(cmds.xform(insertion, query=True, worldSpace=True, translation=True))
        driverPos = om.MVector(cmds.xform(driver, query=True, worldSpace=True, translation=True))
        muscleLength = (insertionPos - originPos).length()
        if muscleLength <= 0:
            raise ValueError("Source muscle endpoints must have different positions.")

        mirrored = cls(newMuscleName, muscleLength, compressionFactor, stretchFactor,
                       compressionOffset, stretchOffset)
        cmds.parent(mirrored.muscleOrigin, originAttachObj)
        cmds.parent(mirrored.muscleInsertion, insertionAttachObj)
        cmds.parent(mirrored.originLoc, originAttachObj)
        cmds.parent(mirrored.insertionLoc, insertionAttachObj)

        for locator, position in ((mirrored.originLoc, originPos),
                                  (mirrored.insertionLoc, insertionPos),
                                  (mirrored.driverLoc, driverPos)):
            cmds.xform(locator, worldSpace=True, translation=(-position.x, position.y, position.z))

        return mirrored

# ==========================================================
# TEST
# ==========================================================
