using UnrealBuildTool;

public class SailingSim : ModuleRules
{
	public SailingSim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "SailingPhysics"
		});

		PrivateDependencyModuleNames.AddRange(new string[] {
			"RHI"
		});
	}
}
