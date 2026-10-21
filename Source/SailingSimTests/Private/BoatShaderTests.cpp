#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Internationalization/Regex.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags BoatShaderFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

/**
 * docs/lee-topside-patch/: the boats' shared shader (make_materials.py BOAT_CODE, M_BoatSurface and M_BoatMast) has no
 * conditional between two bare literals. DXC makes one a double, Metal's ray-tracing hit shaders refuse FP64 ("Unhandled
 * FP64 usage"), and the material fell back to the default on High (every AI boat, the ghost and the marina's boats).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualBoatShaderLiteralsTest, "SailingSim.Visual.BoatShaderLiterals", BoatShaderFlags)
bool FVisualBoatShaderLiteralsTest::RunTest(const FString& Parameters)
{
	FString Script;
	if (!FFileHelper::LoadFileToString(Script, *FPaths::Combine(FPaths::ProjectDir(), TEXT("scripts/make_materials.py"))))
	{
		AddWarning(TEXT("scripts/make_materials.py not found"));
		return true;
	}
	const int32 Start = Script.Find(TEXT("BOAT_CODE = r\"\"\""));
	if (!TestTrue(TEXT("BOAT_CODE found"), Start != INDEX_NONE)) return false;
	const int32 End = Script.Find(TEXT("\"\"\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start + 16);
	const FString Code = Script.Mid(Start, End - Start);
	FRegexMatcher Literal(FRegexPattern(TEXT("\\?\\s*-?[0-9]+(\\.[0-9]+)?\\s*:\\s*-?[0-9]+(\\.[0-9]+)?(?![0-9.f])")), Code);
	int32 Found = 0;
	while (Literal.FindNext())
	{
		++Found;
		AddError(FString::Printf(TEXT("BOAT_CODE: a conditional between bare literals (type them, 0.5f): %s"), *Literal.GetCaptureGroup(0)));
	}
	TestEqual(TEXT("bare-literal conditionals in BOAT_CODE"), Found, 0);
	return true;
}

#endif
