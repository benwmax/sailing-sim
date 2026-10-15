#include "WeatherDay.h"
#include "SailingMath.h"
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <sstream>

namespace Sailing
{
	namespace
	{
		constexpr const char* kBinaryMarker = "RADARBIN\n";
	}

	bool FWeatherDay::LoadFromMemory(const uint8_t* Data, size_t Size, std::string* OutError)
	{
		auto Fail = [&](const std::string& Why) { if (OutError) *OutError = Why; return false; };
		if (!Data || Size < 8 || std::memcmp(Data, "WXDAY 1", 7) != 0) return Fail("not a WXDAY 1 file");
		// The text header runs to the radar marker (or the end).
		size_t TextEnd = Size;
		const size_t MarkerLen = std::strlen(kBinaryMarker);
		for (size_t I = 0; I + MarkerLen <= Size; ++I)
		{
			if (Data[I] == 'R' && std::memcmp(Data + I, kBinaryMarker, MarkerLen) == 0) { TextEnd = I; break; }
		}
		*this = FWeatherDay();
		std::istringstream In(std::string(reinterpret_cast<const char*>(Data), TextEnd));
		std::string Line;
		size_t Frames = 0;
		while (std::getline(In, Line))
		{
			if (Line.empty() || Line[0] == '#') continue;
			std::istringstream L(Line);
			std::string Key;
			L >> Key;
			if (Key == "date") L >> Date;
			else if (Key == "place") L >> Place;
			else if (Key == "title") { std::getline(L, Title); if (!Title.empty() && Title[0] == ' ') Title.erase(0, 1); }
			else if (Key == "utc_offset") L >> UtcOffset;
			else if (Key == "start_hour") L >> StartHour;
			else if (Key == "hour")
			{
				int H = 0;
				FWeatherHour R;
				L >> H >> R.WindKnots >> R.FromDegrees >> R.GustKnots >> R.AirC >> R.DewC >> R.WaterC >> R.MixedLayerM >> R.CapeJkg
					>> R.CloudLow >> R.CloudMid >> R.CloudHigh >> R.CloudBaseM >> R.RainMmPerHour >> R.VisibilityKm;
				if (!L || H != int(Hours.size())) return Fail("bad hour line: " + Line);
				Hours.push_back(R);
			}
			else if (Key == "storm")
			{
				bStorm = true;
				std::string K;
				double V;
				while (L >> K >> V)
				{
					if (K == "arrival") StormArrivalHour = V;
					else if (K == "move") StormMoveDegrees = V;
					else if (K == "speed") StormSpeedMs = V;
					else if (K == "cold_pool") ColdPoolDeltaC = V;
					else if (K == "depth") ColdPoolDepthM = V;
					else if (K == "peak_gust") PeakGustKnots = V;
					else if (K == "burst") BurstPeakMs = V;
					else if (K == "peak_rain") PeakRainMmPerHour = V;
					else if (K == "time_scale") StormTimeScale = V;
				}
			}
			else if (Key == "radar") L >> RadarNx >> RadarNy >> RadarCellM >> Frames;
			else if (Key == "radar_hours")
			{
				double H;
				while (L >> H) RadarHours.push_back(H);
			}
		}
		if (Hours.size() != 24) return Fail("expected 24 hours");
		if (Frames > 0)
		{
			const size_t Need = size_t(RadarNx) * size_t(RadarNy) * Frames;
			if (RadarHours.size() != Frames || RadarNx <= 0 || RadarNy <= 0 || TextEnd + MarkerLen + Need > Size) return Fail("bad radar block");
			Radar.assign(Data + TextEnd + MarkerLen, Data + TextEnd + MarkerLen + Need);
		}
		else
		{
			RadarNx = RadarNy = 0;
			RadarHours.clear();
		}
		return true;
	}

	bool FWeatherDay::LoadFile(const std::string& Path, std::string* OutError)
	{
		std::ifstream In(Path, std::ios::binary);
		if (!In)
		{
			if (OutError) *OutError = "cannot open " + Path;
			return false;
		}
		const std::vector<uint8_t> Bytes((std::istreambuf_iterator<char>(In)), std::istreambuf_iterator<char>());
		return LoadFromMemory(Bytes.data(), Bytes.size(), OutError);
	}

	int FWeatherDay::Year() const { return Date.size() >= 10 ? std::atoi(Date.substr(0, 4).c_str()) : 2024; }
	int FWeatherDay::Month() const { return Date.size() >= 10 ? std::atoi(Date.substr(5, 2).c_str()) : 6; }
	int FWeatherDay::DayOfMonth() const { return Date.size() >= 10 ? std::atoi(Date.substr(8, 2).c_str()) : 1; }

	FWeatherHour FWeatherDay::At(double LocalHour) const
	{
		if (Hours.empty()) return FWeatherHour();
		const double H = Clamp(LocalHour, 0.0, 23.0);
		const int I = std::min(int(H), 22);
		const double F = H - I;
		const FWeatherHour& A = Hours[size_t(I)];
		const FWeatherHour& B = Hours[size_t(I + 1)];
		FWeatherHour R;
		auto Mix = [F](double X, double Y) { return X + (Y - X) * F; };
		R.WindKnots = Mix(A.WindKnots, B.WindKnots);
		// Direction as a vector average weighted by speed (a light wind's direction matters less), the short way round.
		const double Ax = A.WindKnots * std::cos(A.FromDegrees * kDegToRad), Ay = A.WindKnots * std::sin(A.FromDegrees * kDegToRad);
		const double Bx = B.WindKnots * std::cos(B.FromDegrees * kDegToRad), By = B.WindKnots * std::sin(B.FromDegrees * kDegToRad);
		const double Vx = Mix(Ax, Bx), Vy = Mix(Ay, By);
		R.FromDegrees = (std::fabs(Vx) + std::fabs(Vy) > 1e-6) ? std::fmod(std::atan2(Vy, Vx) * kRadToDeg + 360.0, 360.0) : A.FromDegrees;
		R.GustKnots = Mix(A.GustKnots, B.GustKnots);
		R.AirC = Mix(A.AirC, B.AirC);
		R.DewC = Mix(A.DewC, B.DewC);
		R.WaterC = Mix(A.WaterC, B.WaterC);
		R.MixedLayerM = Mix(A.MixedLayerM, B.MixedLayerM);
		R.CapeJkg = Mix(A.CapeJkg, B.CapeJkg);
		R.CloudLow = Mix(A.CloudLow, B.CloudLow);
		R.CloudMid = Mix(A.CloudMid, B.CloudMid);
		R.CloudHigh = Mix(A.CloudHigh, B.CloudHigh);
		R.CloudBaseM = Mix(A.CloudBaseM, B.CloudBaseM);
		R.RainMmPerHour = Mix(A.RainMmPerHour, B.RainMmPerHour);
		R.VisibilityKm = Mix(A.VisibilityKm, B.VisibilityKm);
		return R;
	}

	double FWeatherDay::RadarRate(double X, double Y, double LocalHour) const
	{
		if (!HasRadar() || LocalHour < RadarHours.front() || LocalHour > RadarHours.back()) return -1.0;
		size_t K = 0;
		while (K + 2 < RadarHours.size() && RadarHours[K + 1] <= LocalHour) ++K;
		const double Span = std::max(RadarHours[K + 1 < RadarHours.size() ? K + 1 : K] - RadarHours[K], 1e-6);
		const double F = RadarHours.size() > 1 ? Clamp((LocalHour - RadarHours[K]) / Span, 0.0, 1.0) : 0.0;
		const double Fr = X / RadarCellM + 0.5 * RadarNx - 0.5, Fc = Y / RadarCellM + 0.5 * RadarNy - 0.5;
		if (Fr < 0.0 || Fc < 0.0 || Fr > RadarNx - 1.0 || Fc > RadarNy - 1.0) return -1.0;
		const int R0 = std::min(int(Fr), RadarNx - 2), C0 = std::min(int(Fc), RadarNy - 2);
		const double Tr = Fr - R0, Tc = Fc - C0;
		auto Frame = [&](size_t Index)
		{
			const uint8_t* P = Radar.data() + Index * size_t(RadarNx) * size_t(RadarNy);
			auto V = [&](int R, int C) { return 0.5 * P[size_t(R) * RadarNy + C]; };
			return Lerp(Lerp(V(R0, C0), V(R0, C0 + 1), Tc), Lerp(V(R0 + 1, C0), V(R0 + 1, C0 + 1), Tc), Tr);
		};
		const size_t K1 = std::min(K + 1, RadarHours.size() - 1);
		return Lerp(Frame(K), Frame(K1), F);
	}
}
