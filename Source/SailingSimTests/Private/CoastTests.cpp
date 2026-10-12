#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "Chart.h"
#include "LakeData.h"
#include "Lights.h"
#include "Navigation.h"
#include "Tides.h"
#include "SailingEnvironment.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** The Galveston Bay bake, loaded once for all the coast tests. */
	const FLakeData& Galveston()
	{
		static FLakeData Lake;
		static bool bLoaded = Lake.Load(FLakeData::DefaultDirectory(), TEXT("GalvestonBay"));
		return Lake;
	}

	/** The NOAA reference predictions the bake saved beside the data (CO-OPS API, times in GMT). */
	TSharedPtr<FJsonObject> References()
	{
		FString Json;
		TSharedPtr<FJsonObject> Root;
		if (FFileHelper::LoadFileToString(Json, *(FLakeData::DefaultDirectory() / TEXT("GalvestonBay.json"))))
		{
			FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root);
		}
		return Root.IsValid() ? Root->GetObjectField(TEXT("reference_predictions")) : nullptr;
	}

	/** "2026-10-12 05:09" (GMT) to Unix seconds. */
	double ParseGmt(const FString& S)
	{
		return UnixSecondsUtc(FCString::Atoi(*S.Mid(0, 4)), FCString::Atoi(*S.Mid(5, 2)), FCString::Atoi(*S.Mid(8, 2)),
			FCString::Atoi(*S.Mid(11, 2)), FCString::Atoi(*S.Mid(14, 2)));
	}

	const FNavaid* FindAid(const FLakeData& Lake, const TCHAR* Name)
	{
		return Lake.Navaids.FindByPredicate([&](const FNavaid& N) { return N.Name == Name; });
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastTideTimesTest, "SailingSim.Coast.TideTimesMatchNoaa", Flags)
bool FCoastTideTimesTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Galveston();
	const TSharedPtr<FJsonObject> Ref = References();
	if (!TestTrue(TEXT("Galveston Bay and its references load"), Lake.IsTidal() && Ref.IsValid())) return false;
	// Station order in the bake: 8771450 Galveston Pier 21, 8771341 North Jetty, 8771013 Eagle Point, ...
	const TMap<FString, int32> Stations = { { TEXT("8771450"), 0 }, { TEXT("8771013"), 2 } };
	for (const TPair<FString, int32>& Station : Stations)
	{
		const TArray<TSharedPtr<FJsonValue>>& Hilo = Ref->GetObjectField(TEXT("hilo"))->GetArrayField(Station.Key);
		const FTideStation& S = Lake.Tides.HeightStations[Station.Value];
		const double From = ParseGmt(Hilo[0]->AsArray()[0]->AsString()) - 3 * 3600.0;
		const double To = ParseGmt(Hilo.Last()->AsArray()[0]->AsString()) + 3 * 3600.0;
		const std::vector<FTideEvent> Ours = TideExtremes(S, From, To);
		double WorstMinutes = 0.0, WorstHeight = 0.0;
		int32 Matched = 0;
		for (int32 I = 0; I < Hilo.Num(); ++I)
		{
			const TArray<TSharedPtr<FJsonValue>>& E = Hilo[I]->AsArray();
			const double Time = ParseGmt(E[0]->AsString()), Height = E[1]->AsNumber();
			const FTideEvent::EType Type = E[2]->AsString() == TEXT("H") ? FTideEvent::High : FTideEvent::Low;
			const FTideEvent* Best = nullptr;
			for (const FTideEvent& O : Ours) if (O.Type == Type && (!Best || FMath::Abs(O.Time - Time) < FMath::Abs(Best->Time - Time))) Best = &O;
			if (!Best) continue;
			// A flat turn (a small range on either side) has a poorly defined minute; NOAA's tables round too.
			const double PrevH = I > 0 ? Hilo[I - 1]->AsArray()[1]->AsNumber() : Height + 1.0;
			const double NextH = I + 1 < Hilo.Num() ? Hilo[I + 1]->AsArray()[1]->AsNumber() : Height + 1.0;
			const bool bFlat = FMath::Min(FMath::Abs(Height - PrevH), FMath::Abs(Height - NextH)) < 0.1;
			const double Minutes = FMath::Abs(Best->Time - Time) / 60.0;
			if (Minutes <= (bFlat ? 20.0 : 8.0)) ++Matched;
			else AddError(FString::Printf(TEXT("%s %s %s: ours %.0f min off"), *Station.Key, *E[0]->AsString(), *E[2]->AsString(), Minutes));
			if (!bFlat) WorstMinutes = FMath::Max(WorstMinutes, Minutes);
			WorstHeight = FMath::Max(WorstHeight, FMath::Abs(Best->Value - Height));
		}
		AddInfo(FString::Printf(TEXT("%s: %d of %d highs and lows matched; worst %.1f min (well-defined turns), worst height %.1f cm"),
			*Station.Key, Matched, Hilo.Num(), WorstMinutes, WorstHeight * 100.0));
		TestEqual(FString::Printf(TEXT("%s every high and low matches"), *Station.Key), Matched, Hilo.Num());
		TestTrue(FString::Printf(TEXT("%s heights within 2 cm of NOAA"), *Station.Key), WorstHeight < 0.02);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastCurrentTimesTest, "SailingSim.Coast.CurrentTimesMatchNoaa", Flags)
bool FCoastCurrentTimesTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Galveston();
	const TSharedPtr<FJsonObject> Ref = References();
	if (!TestTrue(TEXT("Current station and references load"), Lake.Tides.bHasCurrent && Ref.IsValid())) return false;
	const TArray<TSharedPtr<FJsonValue>>& Events = Ref->GetArrayField(TEXT("current_max_slack"));
	const double From = ParseGmt(Events[0]->AsArray()[0]->AsString()) - 3 * 3600.0;
	const double To = ParseGmt(Events.Last()->AsArray()[0]->AsString()) + 3 * 3600.0;
	const std::vector<FTideEvent> Ours = CurrentEvents(Lake.Tides.CurrentStation, From, To);
	int32 Slacks = 0, SlackOk = 0, Strong = 0, StrongOk = 0;
	double WorstSlack = 0.0, WorstMax = 0.0, WorstSpeed = 0.0;
	for (const TSharedPtr<FJsonValue>& V : Events)
	{
		const TArray<TSharedPtr<FJsonValue>>& E = V->AsArray();
		const double Time = ParseGmt(E[0]->AsString()), Speed = E[2]->AsNumber();
		const FString Kind = E[1]->AsString();
		const FTideEvent::EType Type = Kind == TEXT("slack") ? FTideEvent::Slack : (Kind == TEXT("flood") ? FTideEvent::High : FTideEvent::Low);
		// Weak maxima (under 0.3 m/s, about 0.6 kn) are broad plateaus whose minute means little; the gate is slack and the strong runs.
		if (Type != FTideEvent::Slack && FMath::Abs(Speed) < 0.3) continue;
		const FTideEvent* Best = nullptr;
		for (const FTideEvent& O : Ours) if (O.Type == Type && (!Best || FMath::Abs(O.Time - Time) < FMath::Abs(Best->Time - Time))) Best = &O;
		const double Minutes = Best ? FMath::Abs(Best->Time - Time) / 60.0 : 1e9;
		if (Type == FTideEvent::Slack)
		{
			++Slacks;
			SlackOk += Minutes <= 10.0;
			WorstSlack = FMath::Max(WorstSlack, Minutes);
		}
		else
		{
			++Strong;
			// A double-humped run has two near-equal peaks: NOAA may list the other one. Then our current at NOAA's
			// minute must be within 3 cm/s of its maximum (the plateau is the same; only the chosen hump differs).
			const bool bPlateau = FMath::Abs(PredictTide(Lake.Tides.CurrentStation, Time) - Speed) < 0.03;
			StrongOk += (Minutes <= 20.0 || bPlateau) && FMath::Abs(Best->Value - Speed) < 0.05;
			WorstMax = FMath::Max(WorstMax, Minutes);
			if (Best) WorstSpeed = FMath::Max(WorstSpeed, FMath::Abs(Best->Value - Speed));
		}
	}
	AddInfo(FString::Printf(TEXT("Slack: %d of %d within 10 min (worst %.1f). Max flood/ebb: %d of %d within 20 min and 0.05 m/s (worst %.1f min, %.3f m/s)"),
		SlackOk, Slacks, WorstSlack, StrongOk, Strong, WorstMax, WorstSpeed));
	TestTrue(TEXT("Reference has slacks and strong runs"), Slacks >= 10 && Strong >= 10);
	TestEqual(TEXT("Every slack within 10 minutes of NOAA"), SlackOk, Slacks);
	TestEqual(TEXT("Every strong maximum within 20 minutes (or on the same plateau) and 0.05 m/s of NOAA"), StrongOk, Strong);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastLightRhythmTest, "SailingSim.Coast.LightsFlashTheirCharacteristics", Flags)
bool FCoastLightRhythmTest::RunTest(const FString& Parameters)
{
	// Duty cycle and flash count over one period, sampled every 10 ms.
	auto Measure = [](const FLightCharacter& L, int32& OutFlashes, double& OutOn)
	{
		OutFlashes = 0;
		OutOn = 0.0;
		bool bPrev = L.IsOn(L.CycleLength() - 0.005);
		for (double T = 0.0; T < L.CycleLength() - 1e-6; T += 0.01)
		{
			const bool bOn = L.IsOn(T);
			if (bOn && !bPrev) ++OutFlashes;
			if (bOn) OutOn += 0.01;
			bPrev = bOn;
		}
	};
	struct FCase { int Litchr; const char* Group; double Period; int Colour; const char* Label; int Flashes; double On; };
	const FCase Cases[] = {
		{ 2, "(1)", 4.0, 4, "Fl G 4s", 1, 0.4 },        // flashing: 0.4 s
		{ 2, "(2)", 6.0, 3, "Fl(2) R 6s", 2, 0.8 },     // group flashing: two 0.4 s flashes 0.6 s apart
		{ 4, "(1)", 1.0, 4, "Q G 1s", 1, 0.3 },         // quick: 60 a minute
		{ 7, "", 6.0, 1, "Iso W 6s", 1, 3.0 },          // isophase: equal light and dark
		{ 8, "(1)", 4.0, 1, "Oc W 4s", 1, 3.0 },        // occulting: light longer than dark
		{ 3, "(1)", 10.0, 1, "LFl W 10s", 1, 2.0 },     // long flash: 2 s
		{ 12, "(A)", 8.0, 1, "Mo(A) W 8s", 2, 1.6 },    // Morse A: dot 0.4 s, dash 1.2 s
	};
	for (const FCase& C : Cases)
	{
		FLightCharacter L;
		L.Litchr = C.Litchr;
		L.SetGroup(C.Group);
		L.Period = C.Period;
		L.Colours = { C.Colour };
		int32 Flashes = 0;
		double On = 0.0;
		Measure(L, Flashes, On);
		TestEqual(FString::Printf(TEXT("%hs label"), C.Label), FString(UTF8_TO_TCHAR(L.Label().c_str())), FString(UTF8_TO_TCHAR(C.Label)));
		TestEqual(FString::Printf(TEXT("%hs flashes per period"), C.Label), Flashes, C.Flashes);
		TestTrue(FString::Printf(TEXT("%hs light %.2f s of %.0f s (want %.1f)"), C.Label, On, C.Period, C.On), FMath::Abs(On - C.On) < 0.05);
	}

	// Every lit aid in Galveston Bay: shows its period, and a flashing light is dark more than it is lit.
	const FLakeData& Lake = Galveston();
	int32 Lit = 0, Ok = 0;
	for (const FNavaid& N : Lake.Navaids)
	{
		if (!N.bLit) continue;
		++Lit;
		int32 Flashes = 0;
		double On = 0.0;
		Measure(N.Light, Flashes, On);
		const bool bFlashing = N.Light.Litchr >= 2 && N.Light.Litchr <= 6;
		const bool bPeriod = N.Light.Period <= 0.0 || FMath::Abs(N.Light.CycleLength() - N.Light.Period) < 1e-6;
		Ok += bPeriod && (!bFlashing || (Flashes >= 1 && On < 0.5 * N.Light.CycleLength()));
	}
	AddInfo(FString::Printf(TEXT("%d lit aids, %d with a consistent rhythm"), Lit, Ok));
	TestTrue(TEXT("Over 200 lit aids"), Lit > 200);
	TestEqual(TEXT("Every lit aid's rhythm fits its charted character"), Ok, Lit);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastChartSymbolsTest, "SailingSim.Coast.ChartSymbolsMatchNoaaChart", Flags)
bool FCoastChartSymbolsTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Galveston();
	if (!TestTrue(TEXT("Galveston Bay loads"), Lake.Navaids.Num() > 500)) return false;
	// Read from the ENC cells directly (US5HOUCF, US5HOUBG, US4TX1NJ: BOYSHP, COLOUR, CATLAM and the LIGHTS record).
	struct FExpect { const TCHAR* Name; SailingChart::ESymbol Symbol; const TCHAR* Label; bool bGreen; };
	const FExpect Expect[] = {
		{ TEXT("Clear Creek Channel Buoy 19"), SailingChart::ESymbol::Can, TEXT("G C \"19\""), true },
		{ TEXT("Clear Creek Channel Buoy 18"), SailingChart::ESymbol::Nun, TEXT("R N \"18\""), false },
		{ TEXT("Clear Creek Channel Lighted Buoy 11"), SailingChart::ESymbol::Pillar, TEXT("Fl G 1s \"11\""), true },
		{ TEXT("Houston Ship Channel Lighted Buoy 34"), SailingChart::ESymbol::Pillar, TEXT("Fl R 4s \"34\""), false },
		{ TEXT("Clear Creek Channel Light 2"), SailingChart::ESymbol::Beacon, TEXT("Fl R 6s 17ft 4M \"2\""), false },
		{ TEXT("Clear Creek Channel Light 23"), SailingChart::ESymbol::Beacon, TEXT("Q G 1s 17ft 4M \"23\""), true },
		{ TEXT("Clear Creek Channel Daybeacon 7"), SailingChart::ESymbol::Beacon, TEXT("G \"7\""), true },
	};
	for (const FExpect& E : Expect)
	{
		const FNavaid* N = FindAid(Lake, E.Name);
		if (!TestNotNull(E.Name, N)) continue;
		TestEqual(FString::Printf(TEXT("%s symbol"), E.Name), int32(SailingChart::SymbolFor(*N)), int32(E.Symbol));
		TestEqual(FString::Printf(TEXT("%s label"), E.Name), SailingChart::AidLabel(*N), FString(E.Label));
		const FLinearColor C = SailingChart::AidColour(*N);
		TestTrue(FString::Printf(TEXT("%s drawn %s"), E.Name, E.bGreen ? TEXT("green") : TEXT("red")), E.bGreen ? C.G > C.R : C.R > C.G);
	}

	// The U.S. lateral system across the whole bay ("red right returning"): port-hand aids green with odd numbers,
	// starboard-hand red with even numbers; unlit port buoys cans, unlit starboard buoys nuns.
	int32 Lateral = 0, Consistent = 0;
	for (const FNavaid& N : Lake.Navaids)
	{
		if (N.CatLam != 1 && N.CatLam != 2) continue;
		const FString Number = SailingChart::AidNumber(N);
		if (Number.IsEmpty() || !FChar::IsDigit(Number[0])) continue;
		++Lateral;
		const bool bPort = N.CatLam == 1;
		const FLinearColor C = SailingChart::AidColour(N);
		const bool bOdd = FCString::Atoi(*Number) % 2 == 1;
		const SailingChart::ESymbol S = SailingChart::SymbolFor(N);
		const bool bShape = N.Kind != TEXT("buoy") || N.bLit || S == (bPort ? SailingChart::ESymbol::Can : SailingChart::ESymbol::Nun);
		if (bPort == bOdd && (bPort ? C.G > C.R : C.R > C.G) && bShape) ++Consistent;
		else AddWarning(FString::Printf(TEXT("%s does not follow the lateral system"), *N.Name));
	}
	AddInfo(FString::Printf(TEXT("%d numbered lateral aids, %d consistent"), Lateral, Consistent));
	TestTrue(TEXT("Over 150 numbered lateral aids"), Lateral > 150);
	TestEqual(TEXT("All follow the lateral system"), Consistent, Lateral);

	// Soundings: printed in feet, rounded down; drying heights underlined.
	TestEqual(TEXT("2.4 m prints 7 ft"), SailingChart::SoundingText(2.4), FString(TEXT("7")));
	TestEqual(TEXT("-0.3 m dries 1 ft"), SailingChart::SoundingText(-0.3), FString(TEXT("_1")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastDepthsTest, "SailingSim.Coast.DepthsMatchChartSoundings", Flags)
bool FCoastDepthsTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Galveston();
	FChartData Chart;
	if (!TestTrue(TEXT("Chart loads"), Lake.IsLoaded() && Chart.Load(FLakeData::DefaultDirectory() / TEXT("GalvestonBay.chart.json")))) return false;
	// The terrain is at chart datum when the level offset is zero (MLLW): its depth at each sounding should match.
	TArray<double> Errors;
	for (const FVector3d& S : Chart.Soundings)
	{
		if (S.Z <= 0.0) continue;
		Errors.Add(FMath::Abs(-Lake.Terrain.HeightAt(S.X, S.Y) - S.Z));
	}
	Errors.Sort();
	const double Median = Errors[Errors.Num() / 2], P90 = Errors[Errors.Num() * 9 / 10];
	AddInfo(FString::Printf(TEXT("%d soundings: median error %.2f m, 90th percentile %.2f m"), Errors.Num(), Median, P90));
	TestTrue(TEXT("Over 3000 soundings"), Errors.Num() > 3000);
	TestTrue(TEXT("Median within 0.15 m"), Median < 0.15);
	TestTrue(TEXT("90% within 0.6 m"), P90 < 0.6);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastFixTest, "SailingSim.Coast.PlottedFixesLandWithinTolerance", Flags)
bool FCoastFixTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Galveston();
	if (!TestTrue(TEXT("Galveston Bay loads"), Lake.Navaids.Num() > 500)) return false;
	const double Var = Lake.VariationDeg;
	FRandomStream Random(7);
	// Positions around the bay; three bearings on the nearest well-spread aids, read to the whole degree.
	const FVector2D Positions[] = { FVector2D(500, 1500), FVector2D(-3000, 6000), FVector2D(-12000, 14000), FVector2D(-20000, 18000), FVector2D(6000, 8000) };
	double WorstExact = 0.0, WorstNoisy = 0.0;
	for (const FVector2D& Me : Positions)
	{
		TArray<const FNavaid*> Aids;
		for (const FNavaid& N : Lake.Navaids) if (FVector2D::Distance(Me, FVector2D(N.X, N.Y)) < 5556.0) Aids.Add(&N);
		Aids.Sort([&](const FNavaid& A, const FNavaid& B) { return FVector2D::DistSquared(Me, FVector2D(A.X, A.Y)) < FVector2D::DistSquared(Me, FVector2D(B.X, B.Y)); });
		for (const double Noise : { 0.0, 2.0 })
		{
			SailingNav::FPlot Plot;
			Plot.Start(Me + FVector2D(800, 800), 0.0);
			TArray<double> Taken;
			bool bFix = false;
			for (const FNavaid* N : Aids)
			{
				const double True = SailingNav::BearingDeg(Me, FVector2D(N->X, N->Y));
				bool bSpread = true;
				for (double T : Taken) { const double Cut = FMath::Abs(FMath::Fmod(True - T + 360.0, 180.0)); if (Cut < 40.0 || Cut > 140.0) bSpread = false; }
				if (!bSpread) continue;
				Taken.Add(True);
				SailingNav::FBearing B;
				B.ObjectName = N->Name;
				B.Object = FVector2D(N->X, N->Y);
				B.MagneticDeg = FMath::RoundToDouble(SailingNav::TrueToMagnetic(True, Var) + Random.FRandRange(-Noise, Noise));
				B.Time = Taken.Num() * 30.0;
				bFix |= Plot.AddBearing(B, Var);
				if (Taken.Num() == 3) break;
			}
			if (!TestTrue(TEXT("A fix was plotted"), bFix && Plot.bHasFix)) continue;
			const double Error = FVector2D::Distance(Plot.Fix, Me);
			(Noise > 0.0 ? WorstNoisy : WorstExact) = FMath::Max(Noise > 0.0 ? WorstNoisy : WorstExact, Error);
		}
	}
	AddInfo(FString::Printf(TEXT("Worst fix error: %.0f m with bearings read to the degree, %.0f m with +-2 degree compass error"), WorstExact, WorstNoisy));
	TestTrue(TEXT("Read to the degree: within 0.05 nm (93 m)"), WorstExact < 93.0);
	TestTrue(TEXT("With +-2 degree error: within 0.2 nm (370 m)"), WorstNoisy < 370.0);

	// Variation: east is least (magnetic = true - east) and a bearing round-trips.
	// The chart's compass rose near Kemah: 2 deg 01' E in 2021, decreasing 6.5' a year, so about 1 deg 28' E in 2026.
	TestTrue(TEXT("Variation is about 1.5 E in 2026 (the compass rose near Kemah)"), Var > 1.3 && Var < 1.6);
	TestTrue(TEXT("090 T is 088.5 M"), FMath::Abs(SailingNav::TrueToMagnetic(90.0, Var) - (90.0 - Var)) < 1e-9);

	// Dead reckoning: 10 minutes at 5 knots on 090 T puts you 0.83 nm east.
	SailingNav::FPlot Dr;
	Dr.Start(FVector2D::ZeroVector, 0.0);
	for (int32 I = 0; I < 600; ++I) Dr.Advance(90.0, 5.0 * kKnot, 1.0, I + 1.0);
	TestTrue(TEXT("DR 5 kn x 10 min east = 1543 m"), FMath::Abs(Dr.Dr.Y - 1543.3) < 1.0 && FMath::Abs(Dr.Dr.X) < 1.0);
	TestTrue(TEXT("DR track marked every 30 s"), Dr.DrTrack.Num() == 21);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastCurrentSetsBoatTest, "SailingSim.Coast.CurrentSetsTheBoat", Flags)
bool FCoastCurrentSetsBoatTest::RunTest(const FString& Parameters)
{
	// A J/22 lying with sails slack in a 1.5 kn current setting 296 T (the bay's flood): she drifts with it, and the log reads zero.
	FWindParams P;
	P.SpeedKnots = 0.0;
	const FWindField Calm(P);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, 0.0, 0.0);
	const double Set = FMath::DegreesToRadians(296.0), Drift = 1.5 * kKnot;
	const Vec3 Current(FMath::Cos(Set), FMath::Sin(Set), 0.0);
	Boat.SetWaterCurrent(Current * Drift);
	// She has been lying in this stream a while: moving with the water, not a standing start against it.
	Boat.GetMutableState().Velocity = Current * Drift;
	FBoatControls C;
	C.MainSheet = 1.0;
	C.JibSheet = 1.0;
	for (int32 I = 0; I < int32(120.0 * PhysicsHz); ++I) Boat.Step(PhysicsDt, C, Calm);
	const Vec3 V = Boat.GetState().Velocity;
	const double Sog = FMath::Sqrt(V.X * V.X + V.Y * V.Y);
	const double Cog = SailingNav::NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(V.Y, V.X)));
	AddInfo(FString::Printf(TEXT("After 2 min: %.2f kn over the ground toward %.0f T, log %.2f kn"), Sog / kKnot, Cog, Boat.GetTelemetry().SpeedThroughWater / kKnot));
	TestTrue(TEXT("Drifts at the current's speed (within 10%)"), FMath::Abs(Sog - Drift) < 0.1 * Drift);
	TestTrue(TEXT("Drifts in the current's direction (within 5 degrees)"), FMath::Abs(FMath::UnwindDegrees(Cog - 296.0)) < 5.0);
	TestTrue(TEXT("The log (speed through the water) reads near zero"), FMath::Abs(Boat.GetTelemetry().SpeedThroughWater) < 0.1 * kKnot);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCoastSunTimesTest, "SailingSim.Coast.SunRisesAndSetsOnTime", Flags)
bool FCoastSunTimesTest::RunTest(const FString& Parameters)
{
	// Galveston (29.30 N, 94.80 W) on 12 August 2026 (day 224), CDT (UTC-5): sunrise 06:46, sunset 20:02 (published
	// tables, weather-stats.com; the sun's upper limb with refraction, elevation -0.833 deg).
	auto Elevation = [](double Hour, int32 Day) { double E = 0.0, A = 0.0; ASailingEnvironment::SunPosition(Hour, Day, 29.30, -94.80, -5.0, E, A); return E; };
	auto Crossing = [&](double From, double To, int32 Day)
	{
		double A = From, B = To;
		for (int32 I = 0; I < 40; ++I) { const double M = 0.5 * (A + B); ((Elevation(A, Day) + 0.833 > 0.0) == (Elevation(M, Day) + 0.833 > 0.0) ? A : B) = M; }
		return 0.5 * (A + B);
	};
	auto Fmt = [](double H) { return FString::Printf(TEXT("%02d:%02d"), int32(H), int32(FMath::Fmod(H, 1.0) * 60.0 + 0.5)); };
	const double Rise = Crossing(4.0, 13.0, 224), Set = Crossing(13.5, 23.0, 224);
	AddInfo(FString::Printf(TEXT("12 Aug: sunrise %s, sunset %s CDT"), *Fmt(Rise), *Fmt(Set)));
	TestTrue(TEXT("Sunrise within 4 minutes of 06:46"), FMath::Abs(Rise - (6.0 + 46.0 / 60.0)) < 4.0 / 60.0);
	TestTrue(TEXT("Sunset within 4 minutes of 20:02"), FMath::Abs(Set - (20.0 + 2.0 / 60.0)) < 4.0 / 60.0);
	// Solar noon on 12 October: 12:00 + 6 h 19 min (94.8 W) - 5 h (CDT) - 13.6 min (equation of time) = 13:05.
	double Noon = 12.0, Best = -90.0;
	for (double H = 11.0; H < 15.0; H += 1.0 / 600.0) if (Elevation(H, 285) > Best) { Best = Elevation(H, 285); Noon = H; }
	AddInfo(FString::Printf(TEXT("12 Oct: solar noon %s CDT, sun %.1f deg high"), *Fmt(Noon), Best));
	TestTrue(TEXT("Solar noon within 3 minutes of 13:05"), FMath::Abs(Noon - (13.0 + 5.0 / 60.0)) < 0.05);
	return true;
}

#endif
