| Scope | excl ms/frame A | excl ms/frame B | diff (B - A) | incl ms/frame A | incl ms/frame B | calls/frame A | calls/frame B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Game thread idle time | 3.615 | 3.809 | +0.194 | 3.615 | 3.809 | 1.0 | 1.0 |
| Sailing_BoatCapture | 0.245 | 0.198 | -0.047 | 0.247 | 0.200 | 1.0 | 1.0 |
| ParallelFor Task | 1.787 | 1.826 | +0.038 | 1.787 | 1.826 | 3.0 | 3.0 |
| Sailing_RigLines | 1.147 | 1.174 | +0.027 | 1.487 | 1.507 | 1.1 | 1.1 |
| UpdateSection GT | 0.650 | 0.638 | -0.011 | 0.650 | 0.638 | 6.8 | 6.8 |
| Sailing_WaterUploads | 0.292 | 0.302 | +0.010 | 0.297 | 0.307 | 1.0 | 1.0 |
| Sailing_Water | 0.783 | 0.776 | -0.007 | 1.657 | 1.676 | 1.0 | 1.0 |
| GameEngine Tick | 0.078 | 0.084 | +0.006 | 9.835 | 9.837 | 1.0 | 1.0 |
| Sailing_Crew | 0.305 | 0.309 | +0.005 | 0.316 | 0.321 | 4.0 | 4.0 |
| Create ProcMesh Proxy | 0.119 | 0.115 | -0.004 | 0.124 | 0.117 | 3.7 | 2.9 |
| AddPrimitive (GT) | 0.032 | 0.028 | -0.004 | 0.161 | 0.150 | 4.2 | 3.3 |
| ConstructObject | 0.029 | 0.025 | -0.004 | 0.081 | 0.073 | 6.5 | 5.7 |
| WaitForTasks | 0.143 | 0.139 | -0.004 | 0.143 | 0.139 | 1.1 | 1.1 |
| ParallelFor.Wait | 0.443 | 0.446 | +0.003 | 0.443 | 0.446 | 2.0 | 2.1 |
| UInstancedStaticMeshComponent::CalcBoundsImpl | 0.037 | 0.034 | -0.003 | 0.037 | 0.034 | 0.8 | 0.8 |
| Queue Ticks | 0.066 | 0.069 | +0.003 | 0.066 | 0.069 | 1.0 | 1.0 |
| Create Mesh Section | 0.044 | 0.042 | -0.002 | 0.078 | 0.075 | 2.6 | 2.6 |
| FTaskBase::WaitImpl_StateChangeEvent_WaitFor | 0.021 | 0.023 | +0.002 | 0.021 | 0.023 | 0.1 | 0.1 |
| UInstancedStaticMeshComponent::BatchUpdateInstancesTransforms | 0.204 | 0.202 | -0.002 | 0.204 | 0.202 | 7.0 | 7.0 |
| UpdateChildTransforms | 0.083 | 0.081 | -0.002 | 0.310 | 0.310 | 66.3 | 66.3 |

FEngineLoop::Tick inclusive per frame: A 14.044 ms, B 14.244 ms.
