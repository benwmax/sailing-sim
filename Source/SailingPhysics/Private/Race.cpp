#include "Race.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>
#include <cstdio>

namespace Sailing
{
	namespace
	{
		double Bearing(double FromX, double FromY, double ToX, double ToY) { return std::atan2(ToY - FromY, ToX - FromX); }
		std::string Clock(double Seconds)
		{
			char Buffer[16];
			const int S = int(std::lround(std::max(Seconds, 0.0)));
			std::snprintf(Buffer, sizeof(Buffer), "%d:%02d", S / 60, S % 60);
			return Buffer;
		}
	}

	FRaceCourse FRaceCourse::WindwardLeeward(double LineX, double LineY, double WindFromRad, double BeatLength, double LineLength, int Laps)
	{
		FRaceCourse C;
		C.WindFromRad = WindFromRad;
		const double WX = std::cos(WindFromRad), WY = std::sin(WindFromRad);
		// Facing upwind, starboard is +90 degrees: the committee boat's end.
		const double SX = std::cos(WindFromRad + 0.5 * kPi), SY = std::sin(WindFromRad + 0.5 * kPi);
		C.CommitteeX = LineX + SX * 0.5 * LineLength;
		C.CommitteeY = LineY + SY * 0.5 * LineLength;
		C.PinX = LineX - SX * 0.5 * LineLength;
		C.PinY = LineY - SY * 0.5 * LineLength;
		for (int Lap = 1; Lap <= std::max(Laps, 1); ++Lap)
		{
			FRaceMark W;
			W.X = LineX + WX * BeatLength;
			W.Y = LineY + WY * BeatLength;
			W.Name = "Windward " + std::to_string(Lap);
			C.Marks.push_back(W);
			FRaceMark L;
			L.X = LineX - WX * 80.0;
			L.Y = LineY - WY * 80.0;
			L.Name = "Leeward " + std::to_string(Lap);
			C.Marks.push_back(L);
		}
		return C;
	}

	double FRaceCourse::CourseSide(double X, double Y) const
	{
		const double MX = 0.5 * (CommitteeX + PinX), MY = 0.5 * (CommitteeY + PinY);
		return (X - MX) * std::cos(WindFromRad) + (Y - MY) * std::sin(WindFromRad);
	}

	double FRaceCourse::AlongLine(double X, double Y) const
	{
		const double LX = CommitteeX - PinX, LY = CommitteeY - PinY;
		const double L2 = LX * LX + LY * LY;
		return L2 > 1e-9 ? ((X - PinX) * LX + (Y - PinY) * LY) / L2 : 0.0;
	}

	double FRaceCourse::LineLength() const
	{
		return std::hypot(CommitteeX - PinX, CommitteeY - PinY);
	}

	int FRaceRunner::AddEntry(int VesselId, const std::string& Name)
	{
		FRaceEntry E;
		E.VesselId = VesselId;
		E.Name = Name;
		// Spread the AI's chosen starting spots along the line (the favored end changes with every shift).
		E.StartTarget = 0.2 + 0.6 * std::fmod(0.37 * double(Entries.size() + 1), 1.0);
		Entries.push_back(E);
		return int(Entries.size()) - 1;
	}

	void FRaceRunner::Begin(double Now, double SecondsToStart)
	{
		SequenceStart = Now - (SequenceSeconds - std::clamp(SecondsToStart, 0.0, SequenceSeconds));
		bBegun = true;
		Signals.clear();
		SignalsMade = 0;
		bStartChecked = false;
		bOver = false;
		for (FRaceEntry& E : Entries)
		{
			const int Id = E.VesselId;
			const std::string Name = E.Name;
			const double Target = E.StartTarget;
			E = FRaceEntry();
			E.VesselId = Id;
			E.Name = Name;
			E.StartTarget = Target;
		}
	}

	FRaceRunner::EPhase FRaceRunner::Phase(double Now) const
	{
		if (!bBegun) return EPhase::NotStarted;
		if (bOver) return EPhase::Finished;
		const double T = Now - SequenceStart;
		if (T < 60.0) return EPhase::Warning;
		if (T < 240.0) return EPhase::Preparatory;
		if (T < SequenceSeconds) return EPhase::OneMinute;
		return EPhase::Racing;
	}

	void FRaceRunner::Signal(double Time, const std::string& Text)
	{
		Signals.push_back({ Time, Text });
	}

	FRaceEntry* FRaceRunner::FindEntry(int VesselId)
	{
		for (FRaceEntry& E : Entries) if (E.VesselId == VesselId) return &E;
		return nullptr;
	}

	const FRaceEntry* FRaceRunner::FindEntry(int VesselId) const
	{
		for (const FRaceEntry& E : Entries) if (E.VesselId == VesselId) return &E;
		return nullptr;
	}

	void FRaceRunner::Update(double Now, const std::vector<FVesselSnapshot>& Boats)
	{
		if (!bBegun || bOver) return;
		// The committee's signals (rule 26), each made once, in order.
		struct FSig { double At; const char* Text; };
		static const FSig Sequence[] = {
			{ 0.0, "Warning signal (5:00): class flag up, one sound" },
			{ 60.0, "Preparatory signal (4:00): P flag up, one sound" },
			{ 240.0, "One minute: P flag down, one long sound" },
			{ 300.0, "Start: class flag down, one sound" },
		};
		while (SignalsMade < 4 && Now - SequenceStart >= Sequence[SignalsMade].At)
		{
			// Signals already past when the sequence was joined late are skipped, not replayed.
			if (Now - SequenceStart - Sequence[SignalsMade].At < 2.0) Signal(SequenceStart + Sequence[SignalsMade].At, Sequence[SignalsMade].Text);
			++SignalsMade;
		}

		auto Find = [&](int Id) -> const FVesselSnapshot* { for (const FVesselSnapshot& B : Boats) if (B.Id == Id) return &B; return nullptr; };
		const bool bAfterStart = Now >= StartTime();
		if (bAfterStart && !bStartChecked)
		{
			bStartChecked = true;
			std::string Over;
			for (FRaceEntry& E : Entries)
			{
				const FVesselSnapshot* B = Find(E.VesselId);
				if (!B) continue;
				const double Along = Course.AlongLine(B->X, B->Y);
				// Rule 29.1: any part of her on the course side at the start signal. The bow is half a length ahead.
				const double BowSide = Course.CourseSide(B->X + std::cos(B->Heading) * 0.5 * B->Length, B->Y + std::sin(B->Heading) * 0.5 * B->Length);
				if (BowSide > 0.0 && Along > -0.1 && Along < 1.1)
				{
					E.bOcs = true;
					Over += (Over.empty() ? "" : ", ") + E.Name;
				}
			}
			if (!Over.empty()) Signal(Now, "Individual recall: X flag, one sound. Over early: " + Over);
		}

		bool bAllDone = true;
		for (FRaceEntry& E : Entries)
		{
			const FVesselSnapshot* B = Find(E.VesselId);
			if (!B) continue;
			const double Side = Course.CourseSide(B->X, B->Y);
			const double Along = Course.AlongLine(B->X, B->Y);
			auto CrossedUpwind = [&]() { return E.bHavePrev && E.PrevSide <= 0.0 && Side > 0.0 && Along >= 0.0 && Along <= 1.0; };
			if (bAfterStart && !E.bFinished)
			{
				if (E.bOcs)
				{
					// Back on the pre-start side (wholly): free to start properly.
					if (Side < -0.5 * B->Length) E.bOcs = false;
				}
				else if (!E.bStarted)
				{
					if (CrossedUpwind()) E.bStarted = true;
				}
				else if (E.NextMark < int(Course.Marks.size()))
				{
					const FRaceMark& M = Course.Marks[E.NextMark];
					const double Dist = std::hypot(B->X - M.X, B->Y - M.Y);
					const double Brg = Bearing(M.X, M.Y, B->X, B->Y);
					if (Dist < ZoneRadius)
					{
						if (!E.bInZone) { E.bInZone = true; E.Sweep = 0.0; }
						else
						{
							// A boat cannot sail through a mark: a jump of the bearing (passing over it, or a reset) is not a rounding.
							const double Step = WrapAngle(Brg - E.PrevBearing);
							if (Dist > 3.0 && std::fabs(Step) < 1.2) E.Sweep += Step;
						}
						E.PrevBearing = Brg;
						// Port rounding circles the mark counterclockwise (seen from above): the bearing from the mark falls.
						if (M.bToPort ? E.Sweep <= -RoundingSweep : E.Sweep >= RoundingSweep)
						{
							++E.NextMark;
							E.bInZone = false;
							E.Sweep = 0.0;
							E.bAimPassed = false;
						}
					}
					else
					{
						E.bInZone = false;
						E.Sweep = 0.0;
					}
				}
				else if (CrossedUpwind())
				{
					E.bFinished = true;
					E.FinishTime = Now;
					Signal(Now, E.Name + " finishes (" + Clock(Now - StartTime()) + ")");
				}
			}
			E.PrevSide = Side;
			E.PrevX = B->X;
			E.PrevY = B->Y;
			E.bHavePrev = true;
			bAllDone &= E.bFinished;
		}
		if (bAfterStart && (bAllDone || Now - StartTime() > TimeLimit)) Score(Now);
	}

	void FRaceRunner::Score(double Now)
	{
		std::vector<FRaceEntry*> Finishers;
		for (FRaceEntry& E : Entries) if (E.bFinished) Finishers.push_back(&E);
		std::sort(Finishers.begin(), Finishers.end(), [](const FRaceEntry* A, const FRaceEntry* B) { return A->FinishTime < B->FinishTime; });
		for (size_t I = 0; I < Finishers.size(); ++I)
		{
			Finishers[I]->Place = int(I) + 1;
			Finishers[I]->Points = int(I) + 1;
		}
		const int Penalty = int(Entries.size()) + 1;
		for (FRaceEntry& E : Entries)
		{
			if (E.bFinished) continue;
			E.Points = Penalty;
			E.Status = (E.bOcs && !E.bStarted) ? "OCS" : "DNF";
		}
		bOver = true;
		Signal(Now, "Race over: results posted");
	}

	std::string FRaceRunner::NextTask(const FRaceEntry& E) const
	{
		if (bOver) return E.bFinished ? "Finished: place " + std::to_string(E.Place) : E.Status;
		if (E.bFinished) return "Finished";
		if (E.bOcs) return "Over early: return below the line, then start";
		if (!E.bStarted) return "Start: cross the line between the committee boat and the pin";
		if (E.NextMark < int(Course.Marks.size()))
		{
			const FRaceMark& M = Course.Marks[E.NextMark];
			return "Round " + M.Name + (M.bToPort ? " to port" : " to starboard");
		}
		return "Finish: cross the line upwind";
	}

	FRaceRunner::FTactic FRaceRunner::Tactic(FRaceEntry& E, const FVesselSnapshot& Boat, double Now, double SpeedEstimate) const
	{
		FTactic T;
		const FRaceCourse& C = Course;
		const double WF = C.WindFromRad;
		const double LX = C.CommitteeX - C.PinX, LY = C.CommitteeY - C.PinY;
		const double TX = C.PinX + LX * E.StartTarget, TY = C.PinY + LY * E.StartTarget;
		const double Side = C.CourseSide(Boat.X, Boat.Y);
		const double Speed = std::max(SpeedEstimate, 1.5);
		if (bOver || E.bFinished)
		{
			// Clear the finishing line on a broad reach, at speed (a luffing boat has no steerage to keep clear with).
			const double Along = C.AlongLine(Boat.X, Boat.Y);
			T.Heading = WF + kPi + (Along < 0.5 ? 0.75 : -0.75);
			return T;
		}
		if (Now < StartTime())
		{
			const double Left = StartTime() - Now;
			const double Dist = std::hypot(TX - Boat.X, TY - Boat.Y);
			const double Needed = Dist / (0.7 * Speed) + 10.0;
			if (Left > Needed + 25.0)
			{
				// Hold below the line, reaching back and forth, until it is time to go.
				const double HoldX = TX - std::cos(WF) * 120.0, HoldY = TY - std::sin(WF) * 120.0;
				const double Lateral = (Boat.X - HoldX) * LX / C.LineLength() + (Boat.Y - HoldY) * LY / C.LineLength();
				const double TowardCommittee = std::atan2(LY, LX);
				const double TowardPin = TowardCommittee + kPi;
				if (Side > -50.0) T.Heading = Bearing(Boat.X, Boat.Y, HoldX, HoldY);
				else if (Lateral > 70.0) T.Heading = TowardPin;
				else if (Lateral < -70.0) T.Heading = TowardCommittee;
				else T.Heading = std::fabs(WrapAngle(Boat.Heading - TowardPin)) < std::fabs(WrapAngle(Boat.Heading - TowardCommittee)) ? TowardPin : TowardCommittee;
				return T;
			}
			T.Heading = Bearing(Boat.X, Boat.Y, TX, TY);
			// Early: luff and ease to kill time rather than cross before the gun.
			T.bSlow = Left > Needed + 3.0 || (Side > -2.0 * Boat.Length && Left > 4.0);
			return T;
		}
		if (E.bOcs)
		{
			const double MX = 0.5 * (C.CommitteeX + C.PinX) - std::cos(WF) * 30.0, MY = 0.5 * (C.CommitteeY + C.PinY) - std::sin(WF) * 30.0;
			T.Heading = Bearing(Boat.X, Boat.Y, MX, MY);
			return T;
		}
		if (!E.bStarted)
		{
			// Past the line without crossing it (round an end): back below it first, then across between the ends.
			if (Side > -10.0) T.Heading = Bearing(Boat.X, Boat.Y, TX - std::cos(WF) * 30.0, TY - std::sin(WF) * 30.0);
			else T.Heading = Bearing(Boat.X, Boat.Y, TX + std::cos(WF) * 30.0, TY + std::sin(WF) * 30.0);
			return T;
		}
		if (E.NextMark < int(C.Marks.size()))
		{
			const FRaceMark& M = C.Marks[E.NextMark];
			// The leg after this mark.
			double NX, NY;
			if (E.NextMark + 1 < int(C.Marks.size())) { NX = C.Marks[E.NextMark + 1].X; NY = C.Marks[E.NextMark + 1].Y; }
			else { NX = 0.5 * (C.CommitteeX + C.PinX) + std::cos(WF) * 20.0; NY = 0.5 * (C.CommitteeY + C.PinY) + std::sin(WF) * 20.0; }
			// Each boat rounds on her own line (they would otherwise all aim for the same spot beside the mark).
			const double R = 12.0 + Boat.Length + 9.0 * (E.VesselId % 3);
			const double Sign = M.bToPort ? 1.0 : -1.0;
			if (!E.bAimPassed)
			{
				// Aim beside the mark on the side that leaves it where it must be.
				const double Approach = Bearing(Boat.X, Boat.Y, M.X, M.Y);
				const double AX = M.X + std::cos(Approach + Sign * 0.5 * kPi) * R, AY = M.Y + std::sin(Approach + Sign * 0.5 * kPi) * R;
				if (std::hypot(AX - Boat.X, AY - Boat.Y) < R) E.bAimPassed = true;
				T.Heading = Bearing(Boat.X, Boat.Y, AX, AY);
				if (!E.bAimPassed) return T;
			}
			// Around the mark the right way: step along a circle until the next leg's course leads away from it.
			const double Next = Bearing(M.X, M.Y, NX, NY);
			const double Exit = Next + Sign * 0.5 * kPi;       // bearing from the mark where the next leg leaves the circle
			const double Theta = Bearing(M.X, M.Y, Boat.X, Boat.Y);
			double Remaining = WrapAngle(Sign * (Theta - Exit));
			if (Remaining < 0.0) Remaining += 2.0 * kPi;
			if (Remaining < 0.6 || std::hypot(Boat.X - M.X, Boat.Y - M.Y) > 3.0 * R)
			{
				T.Heading = Bearing(Boat.X, Boat.Y, NX, NY);
				return T;
			}
			const double Step = Theta - Sign * 0.8;
			T.Heading = Bearing(Boat.X, Boat.Y, M.X + std::cos(Step) * R, M.Y + std::sin(Step) * R);
			return T;
		}
		// The finish: up through the line between its ends (from below it; if she is already above, back down first).
		const double MX = 0.5 * (C.CommitteeX + C.PinX), MY = 0.5 * (C.CommitteeY + C.PinY);
		if (Side > -5.0 && E.bHavePrev) T.Heading = Bearing(Boat.X, Boat.Y, MX - std::cos(WF) * 30.0, MY - std::sin(WF) * 30.0);
		else T.Heading = Bearing(Boat.X, Boat.Y, MX + std::cos(WF) * 20.0, MY + std::sin(WF) * 20.0);
		return T;
	}
}
