#include "Lights.h"
#include <cmath>
#include <cstdio>
#include <utility>

namespace Sailing
{
	namespace
	{
		constexpr double kFlash = 0.4, kFlashGap = 0.6, kLongFlash = 2.0;
		constexpr double kDot = 0.4, kDash = 1.2, kMorseGap = 0.4;

		const char* MorseCode(char Letter)
		{
			static const char* Codes[26] = { ".-", "-...", "-.-.", "-..", ".", "..-.", "--.", "....", "..", ".---", "-.-", ".-..", "--",
				"-.", "---", ".--.", "--.-", ".-.", "...", "-", "..-", "...-", ".--", "-..-", "-.--", "--.." };
			return (Letter >= 'A' && Letter <= 'Z') ? Codes[Letter - 'A'] : ".-";
		}

		/** Rhythm of a quick-type light: flash length and the time from one flash to the next. */
		bool QuickRhythm(int Litchr, double& OnTime, double& Spacing)
		{
			switch (Litchr)
			{
			case 4: case 9: OnTime = 0.3; Spacing = 1.0; return true;    // Q, IQ: 60 per minute
			case 5: case 10: OnTime = 0.2; Spacing = 0.5; return true;   // VQ, IVQ: 120 per minute
			case 6: case 11: OnTime = 0.1; Spacing = 0.25; return true;  // UQ, IUQ: 240 per minute
			default: return false;
			}
		}

		int GroupTotal(const std::vector<int>& Groups)
		{
			int Total = 0;
			for (int G : Groups) Total += G;
			return Total > 0 ? Total : 1;
		}
	}

	const char* ColourAbbreviation(int Colour)
	{
		switch (Colour)
		{
		case 1: return "W"; case 2: return "Bu"; case 3: return "R"; case 4: return "G"; case 5: return "Bu"; case 6: return "Y";
		case 7: return "Gy"; case 8: return "Br"; case 9: return "Am"; case 10: return "Vi"; case 11: return "Or"; case 12: return "Mg";
		default: return "W";
		}
	}

	void FLightCharacter::SetGroup(const std::string& SigGrp)
	{
		Groups.clear();
		Morse.clear();
		std::string Inner;
		for (char C : SigGrp) if (C != '(' && C != ')' && C != ' ') Inner += C;
		if (Inner.empty()) return;
		if (Inner[0] >= 'A' && Inner[0] <= 'Z') { Morse = Inner.substr(0, 1); return; }
		size_t Start = 0;
		while (Start <= Inner.size())
		{
			const size_t Plus = Inner.find('+', Start);
			const std::string Part = Inner.substr(Start, Plus == std::string::npos ? std::string::npos : Plus - Start);
			if (!Part.empty()) Groups.push_back(std::atoi(Part.c_str()));
			if (Plus == std::string::npos) break;
			Start = Plus + 1;
		}
	}

	double FLightCharacter::CycleLength() const
	{
		if (Period > 0.0) return Period;
		double On, Spacing;
		if (QuickRhythm(Litchr, On, Spacing)) return Spacing * (Groups.empty() ? 1 : GroupTotal(Groups));
		switch (Litchr)
		{
		case 2: return GroupTotal(Groups) * (kFlash + kFlashGap) + 2.0;
		case 3: return kLongFlash + 4.0;
		default: return 4.0;
		}
	}

	bool FLightCharacter::IsOn(double Time) const
	{
		const double Cycle = CycleLength();
		double T = std::fmod(Time, Cycle);
		if (T < 0.0) T += Cycle;

		// The flashes of a group (or groups, as in Fl(2+1)) at the start of the period, then the long eclipse.
		auto InFlashes = [&](double FlashLength, double Step) -> bool
		{
			std::vector<int> G = Groups.empty() ? std::vector<int>{ 1 } : Groups;
			const double Slot = Cycle / G.size(); // composite groups share the period
			const int Which = std::min(int(T / Slot), int(G.size()) - 1);
			const double Local = T - Which * Slot;
			const int Index = int(Local / Step);
			return Index < G[Which] && Local - Index * Step < FlashLength;
		};

		double On, Spacing;
		if (QuickRhythm(Litchr, On, Spacing))
		{
			if (Groups.empty() && Period <= 0.0) return std::fmod(T, Spacing) < On; // continuous quick
			if (Groups.empty()) return std::fmod(T, Spacing) < On;                  // quick with a charted period
			if (Litchr >= 9 && Litchr <= 11 && Groups.empty()) return T < 0.75 * Cycle && std::fmod(T, Spacing) < On; // interrupted
			return InFlashes(On, Spacing);
		}
		switch (Litchr)
		{
		case 1: return true;                                            // fixed
		case 2: return InFlashes(kFlash, kFlash + kFlashGap);           // flashing, single or grouped
		case 3: return InFlashes(kLongFlash, kLongFlash + 1.0);         // long flash
		case 7: return T < 0.5 * Cycle;                                 // isophase
		case 8:                                                         // occulting: dark briefly, light longer
		{
			const int N = Groups.empty() ? 1 : GroupTotal(Groups);
			if (N == 1) return T < 0.75 * Cycle;
			const double Start = Cycle - N * 1.2;
			if (T < Start) return true;
			return std::fmod(T - Start, 1.2) >= 0.6;
		}
		case 12:                                                        // Morse code
		{
			const char* Code = MorseCode(Morse.empty() ? 'A' : Morse[0]);
			double Cursor = 0.0;
			for (const char* C = Code; *C; ++C)
			{
				const double Length = *C == '-' ? kDash : kDot;
				if (T >= Cursor && T < Cursor + Length) return true;
				Cursor += Length + kMorseGap;
			}
			return false;
		}
		default:                                                        // composite rhythms: shown as single flashes
			return InFlashes(kFlash, kFlash + kFlashGap);
		}
	}

	std::string FLightCharacter::Label() const
	{
		static const char* Names[] = { "", "F", "Fl", "LFl", "Q", "VQ", "UQ", "Iso", "Oc", "IQ", "IVQ", "IUQ", "Mo", "FFl", "Fl+LFl",
			"Oc Fl", "F LFl", "Al Oc", "Al LFl", "Al Fl", "Al Gr", "", "", "", "", "Q+LFl", "VQ+LFl", "UQ+LFl", "Al", "F Al" };
		std::string S = (Litchr > 0 && Litchr < int(sizeof(Names) / sizeof(Names[0]))) ? Names[Litchr] : "F";
		if (!Morse.empty()) S += "(" + Morse + ")";
		else if (!Groups.empty() && !(Groups.size() == 1 && Groups[0] == 1))
		{
			S += "(";
			for (size_t I = 0; I < Groups.size(); ++I) S += (I ? "+" : "") + std::to_string(Groups[I]);
			S += ")";
		}
		for (int Colour : Colours) S += std::string(" ") + ColourAbbreviation(Colour);
		char Buffer[32];
		if (Period > 0.0)
		{
			if (std::fabs(Period - std::round(Period)) < 1e-6) std::snprintf(Buffer, sizeof(Buffer), " %.0fs", Period);
			else std::snprintf(Buffer, sizeof(Buffer), " %.1fs", Period);
			S += Buffer;
		}
		if (HeightM > 0.0)
		{
			std::snprintf(Buffer, sizeof(Buffer), " %.0fft", HeightM / 0.3048);
			S += Buffer;
		}
		if (RangeNm > 0.0)
		{
			std::snprintf(Buffer, sizeof(Buffer), " %.0fM", RangeNm);
			S += Buffer;
		}
		return S;
	}
}
