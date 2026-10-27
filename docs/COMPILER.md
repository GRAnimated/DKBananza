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
