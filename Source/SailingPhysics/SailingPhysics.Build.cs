using UnrealBuildTool;

// Pure C++ boat physics. Depends on Core only: no Engine, no rendering, no UObjects,
// so the same code can be unit-tested headless and stepped at a fixed rate.
public class SailingPhysics : ModuleRules
{
	public SailingPhysics(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		// Never unity-built: each file keeps its own helpers in an anonymous namespace (the physics also builds standalone,
		// file by file). UBT starts unity builds at 32 source files, which the prologue's new file reached.
		bUseUnity = false;
		PublicDependencyModuleNames.AddRange(new string[] { "Core" });
	}
}
