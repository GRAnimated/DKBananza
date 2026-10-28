## Compiler Info

### Speculative devirtualization

Example in `al::ActorPoseKeeperTQMSV::updatePoseTrans`:

```c++
  getQuat = (__int64 (*)(void))vftable->getQuat;
  if ( (char *)getQuat == (char *)al::ActorPoseKeeperTQMSV::getQuat )
  {
    p_mQuat = &this->mQuat;
  }
  else
  {
    v26 = this;
    p_mQuat = (sead::Quatf *)getQuat();
    ...
  }
```

### Inlined implementations

`SequenceStateStage::exeLoad()` is DKB's equivalent of `HakoniwaSequence::exeLoadStage`. DKB only includes it inlined in `anonymous namespace::SequenceStateStageNrvLoad::execute` at `0x710063FAAC`.
