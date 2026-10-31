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
			"RHI", "SailingShaders", "ProceduralMeshComponent", "AudioExtensions", "Json", "MeshDescription", "StaticMeshDescription", "HairStrandsCore", "Slate", "SlateCore", "ApplicationCore", "PhysicsControl", "PhysicsCore", "AssetRegistry", "ImageWrapper"
		});

		// The credits screen reads CREDITS.md at runtime (SailCatalog::Credits): stage the repo's own file into the pak,
		// in every configuration, so it stays the single source.
		RuntimeDependencies.Add("$(ProjectDir)/CREDITS.md", StagedFileType.UFS);

		// Crash and bug reports (docs/sentry): the Sentry plugin exists for the Mac and Win64 only (SailingSim.uproject).
		bool bSentry = Target.Platform == UnrealTargetPlatform.Mac || Target.Platform == UnrealTargetPlatform.Win64;
		if (bSentry) PrivateDependencyModuleNames.Add("Sentry");
		PrivateDefinitions.Add("WITH_SAILING_SENTRY=" + (bSentry ? "1" : "0"));
	}
}
