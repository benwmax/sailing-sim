#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"

class FSailingPhysicsModule : public IModuleInterface
{
public:
	/** W1: loads the shared fine-turbulence tile (Content/TerrainData/Wind.mann) for every wind field. */
	virtual void StartupModule() override;
};
