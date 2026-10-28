using UnrealBuildTool;

// Automation tests (editor only). Run with scripts/test.sh.
public class SailingSimTests : ModuleRules
{
	public SailingSimTests(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		// Never unity-built: each file keeps its own helpers in an anonymous namespace (the physics also builds standalone,
		// file by file). UBT starts unity builds at 32 source files, which the prologue's new file reached.
		bUseUnity = false;

		PrivateDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "SailingPhysics", "SailingSim", "ProceduralMeshComponent", "Json", "InputCore", "MeshDescription", "StaticMeshDescription", "Slate", "SlateCore", "EnhancedInput", "AssetRegistry"
		});
	}
}
