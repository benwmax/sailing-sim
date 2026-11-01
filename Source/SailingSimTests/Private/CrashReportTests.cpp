#include "Misc/AutomationTest.h"
#include "CrashReports.h"
#include "HAL/FileManager.h"

// Crash reports (docs/sentry, #410): with no DSN (every build but a Friday tester build) the plugin stays off and the
// game's edge does nothing, writes nothing and sends nothing; and the log a report carries has the home folder scrubbed.
namespace CrashReportTestsLocal
{
	constexpr EAutomationTestFlags CrashFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCrashReportsInertTest, "SailingSim.Smoke.CrashReportsInert", CrashReportTestsLocal::CrashFlags)
bool FSailingCrashReportsInertTest::RunTest(const FString& Parameters)
{
	TestFalse(TEXT("No DSN: the SDK is not running"), SailCrashReports::IsEnabled());
	const FString Scrubbed = SailCrashReports::ScrubbedLogPath();
	IFileManager::Get().Delete(*Scrubbed, false, true, true);
	SailCrashReports::SetConsent(true);
	SailCrashReports::SetPlace(TEXT("ray-hubbard"), TEXT("J22"));
	SailCrashReports::SetConsent(false);
	TestFalse(TEXT("A yes without an SDK writes no scrubbed log"), IFileManager::Get().FileExists(*Scrubbed));
	TestFalse(TEXT("Still off after consent"), SailCrashReports::IsEnabled());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCrashReportsScrubTest, "SailingSim.Smoke.CrashReportsScrub", CrashReportTestsLocal::CrashFlags)
bool FSailingCrashReportsScrubTest::RunTest(const FString& Parameters)
{
	using SailCrashReports::ScrubPaths;
	TestEqual(TEXT("Mac home"), ScrubPaths(TEXT("LogInit: /Users/ben/Library/Logs/SailingSim.log")), FString(TEXT("LogInit: ~/Library/Logs/SailingSim.log")));
	TestEqual(TEXT("Windows home"), ScrubPaths(TEXT("C:\\Users\\Ben\\AppData\\Local\\SailingSim")), FString(TEXT("~\\AppData\\Local\\SailingSim")));
	TestEqual(TEXT("Windows, forward slashes"), ScrubPaths(TEXT("D:/Users/ben/Saved")), FString(TEXT("~/Saved")));
	TestEqual(TEXT("Linux home"), ScrubPaths(TEXT("/home/ben/.config")), FString(TEXT("~/.config")));
	TestEqual(TEXT("Every occurrence"), ScrubPaths(TEXT("/Users/a/x and /Users/b/y")), FString(TEXT("~/x and ~/y")));
	TestEqual(TEXT("Lines kept"), ScrubPaths(TEXT("/Users/a/x\n/Users/b/y\n")), FString(TEXT("~/x\n~/y\n")));
	TestEqual(TEXT("The bare folder is no home"), ScrubPaths(TEXT("ls /Users/ and /home/")), FString(TEXT("ls /Users/ and /home/")));
	TestEqual(TEXT("Shared folders stay"), ScrubPaths(TEXT("/Users/Shared/Epic Games/UE_5.8")).Contains(TEXT("Epic Games")), true);
	TestEqual(TEXT("A Windows name with a space"), ScrubPaths(TEXT("C:\\Users\\Dana Smith\\AppData\\Local")), FString(TEXT("~\\AppData\\Local")));
	TestEqual(TEXT("A Mac name with a space"), ScrubPaths(TEXT("/Users/Dana Smith/Library/Logs")), FString(TEXT("~/Library/Logs")));
	TestEqual(TEXT("... inside a quoted path"), ScrubPaths(TEXT("open \"C:\\Users\\Dana Smith\\x.log\" failed")), FString(TEXT("open \"~\\x.log\" failed")));
	TestEqual(TEXT("No separator after the name: stop at the space"), ScrubPaths(TEXT("/Users/dana today")), FString(TEXT("~ today")));
	TestEqual(TEXT("... and a later path is not part of the name"), ScrubPaths(TEXT("/Users/dana today /tmp/x")), FString(TEXT("~ today /tmp/x")));
	TestEqual(TEXT("Nothing to scrub"), ScrubPaths(TEXT("LogSailing: world ray-hubbard")), FString(TEXT("LogSailing: world ray-hubbard")));
	return true;
}
