using UnrealBuildTool;

// Automation tests (editor only). Run with scripts/test.sh.
public class SailingSimTests : ModuleRules
{
	public SailingSimTests(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PrivateDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "SailingPhysics", "SailingSim", "ProceduralMeshComponent", "Json", "InputCore", "MeshDescription", "StaticMeshDescription"
		});
	}
}
