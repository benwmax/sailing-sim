using UnrealBuildTool;

// Pure C++ boat physics. Depends on Core only: no Engine, no rendering, no UObjects,
// so the same code can be unit-tested headless and stepped at a fixed rate.
public class SailingPhysics : ModuleRules
{
	public SailingPhysics(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core" });
	}
}
