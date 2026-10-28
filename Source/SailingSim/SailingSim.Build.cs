using UnrealBuildTool;

public class SailingSim : ModuleRules
{
	public SailingSim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "RenderCore", "InputCore", "EnhancedInput", "SailingPhysics"
		});

		PrivateDependencyModuleNames.AddRange(new string[] {
			"RHI", "SailingShaders", "ProceduralMeshComponent", "AudioExtensions", "Json", "MeshDescription", "StaticMeshDescription", "HairStrandsCore", "Slate", "SlateCore", "ApplicationCore", "PhysicsControl", "PhysicsCore", "AssetRegistry"
		});

		// The credits screen reads CREDITS.md at runtime (SailCatalog::Credits): stage the repo's own file into the pak,
		// in every configuration, so it stays the single source.
		RuntimeDependencies.Add("$(ProjectDir)/CREDITS.md", StagedFileType.UFS);
	}
}
