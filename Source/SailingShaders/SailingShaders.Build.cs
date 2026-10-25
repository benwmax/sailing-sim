using UnrealBuildTool;

// docs/sky-probe-readback: the project's own global shaders (Shaders/), mapped to /SailingShaders at PostConfigInit.
public class SailingShaders : ModuleRules
{
	public SailingShaders(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "RHI", "RenderCore" });
		PrivateDependencyModuleNames.AddRange(new string[] { "CoreUObject", "Engine", "Projects" });
	}
}
