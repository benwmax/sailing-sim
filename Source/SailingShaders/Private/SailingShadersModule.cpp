#include "Modules/ModuleManager.h"
#include "Misc/Paths.h"
#include "ShaderCore.h"

class FSailingShadersModule : public IModuleInterface
{
public:
	virtual void StartupModule() override
	{
		AddShaderSourceDirectoryMapping(TEXT("/SailingShaders"), FPaths::Combine(FPaths::ProjectDir(), TEXT("Shaders")));
	}
};

IMPLEMENT_MODULE(FSailingShadersModule, SailingShaders)
