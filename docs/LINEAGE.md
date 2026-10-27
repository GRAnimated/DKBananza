# Changes from Super Mario Odyssey

## LiveActor

After `attackSensor` and `receiveMsg`, there are two new virtuals. I've named them `attackCollider` and `receiveMsgCollider`. `receiveMsgScreenPoint` from Odyssey is gone.

Near the end of the vtable, there's a function that updates the actor's pose and velocity from a physics body. I've named it `updateFromPhysics`.

```c++
al::LiveActor::checkDerivedRuntimeTypeInfo(sead::RuntimeTypeInfo::Interface const*)
al::LiveActor::getRuntimeTypeInfo(void)
al::LiveActor::~LiveActor()
al::LiveActor::~LiveActor()
al::LiveActor::getNerveKeeper(void)
al::LiveActor::init(al::ActorInitInfo const&)
...
al::LiveActor::attackSensor(al::HitSensor *,al::HitSensor *)
al::LiveActor::receiveMsg(al::SensorMsg const*,al::HitSensor *,al::HitSensor *)
al_LiveActor_attackCollider
al_LiveActor_receiveMsgCollider
al::LiveActor::getName(void)
al::LiveActor::getBaseMtx(void)
...
al::LiveActor::initStageSwitchKeeper(void)
al_LiveActor_updateFromPhysics
al::LiveActor::control(void)
al_LiveActor_updateCollider
```

## Screen

`al::getVirtualDisplayWidth`: returns 1280 -> 2280
`al::getVirtualDisplayHeight`: returns 720 -> 1620

## Pose Keeper

There's a new `TQMSV` pose.

## Interfaces

`al::IUseHioNode` now has sead RTTI.

## Nerves

Nerves now use floating point steps and a mutable step rate. Nerve names are now hashed and used in `NerveStateCtrl` comparisons instead of comparing pointers.

After the hash, nerves have one more virtual function. It returns nullptr for most nerves, but some use it to pass extra (sometimes unique) data between nerve calls.

Odyssey:

```c++
class Nerve {
public:
    virtual void execute(NerveKeeper* keeper) const = 0;
    virtual void executeOnEnd(NerveKeeper* keeper) const {}
};
```

Bananza:

```c++
class Nerve {
public:
    virtual void execute(NerveKeeper* keeper) const = 0;
    virtual void executeOnEnd(NerveKeeper* keeper) const {}
    virtual const char* getNameHash() const = 0;
    virtual field_18; // different between nerves
};
```

**NerveKeeper**: Now contains a 2-member vtable due to the inherited `al::IUseHioNode` and stores the previous step and a pointer to the step rate.

Odyssey:

```c++
struct al::NerveKeeper // sizeof=0x30
{
    al::IUseNerve *mParent;
    const al::Nerve *mCurrentNerve;
    const al::Nerve *mNextNerve;
    s32 mStep;
    al::NerveStateCtrl *mStateCtrl;
    al::NerveActionCtrl *mActionCtrl;
};
```

Bananza:

```c++
struct al::NerveKeeper : al::IUseHioNode // sizeof=0x40
{
    // al::HioNode_vtbl __vftable;
    al::IUseNerve *mParent;
    const al::Nerve *mCurrentNerve;
    const al::Nerve *mNextNerve;
    float mStep;
    float mPrevStep;
    const float *mStepRatePtr;
    al::NerveStateCtrl *mStateCtrl;
    void *field_38; // probably mActionCtrl
};
```

## Classes

al::KeyMoveMapPartsGenerator -> VoxelKeyMoveMapPartsGenerator

### Class Sizes

| Class Name | Odyssey Size | Bananza Size |
| ---------- | ------------ | ------------ |
| al::LiveActor | 0x108 | 0x120 |
