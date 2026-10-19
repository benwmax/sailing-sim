#include "GeoAnchor.h"

#include <cmath>
#include <cstdlib>

namespace Sailing
{
	namespace
	{
		constexpr double kDegToRad = 3.14159265358979323846 / 180.0;

		/** The series' constants for GRS80: n, e, the rectifying radius A and Krueger's alpha (forward) and beta
		 *  (inverse) to n^6 (Karney 2011, eqs. 35 and 36). */
		struct FTmSeries
		{
			double E = 0.0;           // first eccentricity
			double RectifyingA = 0.0; // a / (1 + n) (1 + n^2/4 + n^4/64 + n^6/256)
			double Alpha[6] = {};
			double Beta[6] = {};

			FTmSeries()
			{
				const double F = 1.0 / FGeoAnchor::InverseFlattening;
				const double N = F / (2.0 - F);
				const double N2 = N * N;
				const double N3 = N2 * N;
				const double N4 = N3 * N;
				const double N5 = N4 * N;
				const double N6 = N5 * N;
				E = std::sqrt(F * (2.0 - F));
				RectifyingA = FGeoAnchor::SemiMajor / (1.0 + N) * (1.0 + N2 / 4.0 + N4 / 64.0 + N6 / 256.0);
				Alpha[0] = N / 2.0 - 2.0 / 3.0 * N2 + 5.0 / 16.0 * N3 + 41.0 / 180.0 * N4 - 127.0 / 288.0 * N5 + 7891.0 / 37800.0 * N6;
				Alpha[1] = 13.0 / 48.0 * N2 - 3.0 / 5.0 * N3 + 557.0 / 1440.0 * N4 + 281.0 / 630.0 * N5 - 1983433.0 / 1935360.0 * N6;
				Alpha[2] = 61.0 / 240.0 * N3 - 103.0 / 140.0 * N4 + 15061.0 / 26880.0 * N5 + 167603.0 / 181440.0 * N6;
				Alpha[3] = 49561.0 / 161280.0 * N4 - 179.0 / 168.0 * N5 + 6601661.0 / 7257600.0 * N6;
				Alpha[4] = 34729.0 / 80640.0 * N5 - 3418889.0 / 1995840.0 * N6;
				Alpha[5] = 212378941.0 / 319334400.0 * N6;
				Beta[0] = N / 2.0 - 2.0 / 3.0 * N2 + 37.0 / 96.0 * N3 - 1.0 / 360.0 * N4 - 81.0 / 512.0 * N5 + 96199.0 / 604800.0 * N6;
				Beta[1] = 1.0 / 48.0 * N2 + 1.0 / 15.0 * N3 - 437.0 / 1440.0 * N4 + 46.0 / 105.0 * N5 - 1118711.0 / 3870720.0 * N6;
				Beta[2] = 17.0 / 480.0 * N3 - 37.0 / 840.0 * N4 - 209.0 / 4480.0 * N5 + 5569.0 / 90720.0 * N6;
				Beta[3] = 4397.0 / 161280.0 * N4 - 11.0 / 504.0 * N5 - 830251.0 / 7257600.0 * N6;
				Beta[4] = 4583.0 / 161280.0 * N5 - 108847.0 / 3991680.0 * N6;
				Beta[5] = 20648693.0 / 638668800.0 * N6;
			}
		};

		const FTmSeries& Series()
		{
			static const FTmSeries S;
			return S;
		}

		/** tan of the conformal latitude from tan of the geodetic one (Karney eq. 7). */
		double ConformalTan(double Tau, double E)
		{
			const double Sigma = std::sinh(E * std::atanh(E * Tau / std::sqrt(1.0 + Tau * Tau)));
			return Tau * std::sqrt(1.0 + Sigma * Sigma) - Sigma * std::sqrt(1.0 + Tau * Tau);
		}

		/** Unscaled (xi, eta) for a latitude and a longitude from the central meridian, radians. */
		void ForwardXiEta(double Lat, double DLon, double& OutXi, double& OutEta)
		{
			const FTmSeries& S = Series();
			const double TauP = ConformalTan(std::tan(Lat), S.E);
			const double XiP = std::atan2(TauP, std::cos(DLon));
			const double EtaP = std::asinh(std::sin(DLon) / std::sqrt(TauP * TauP + std::cos(DLon) * std::cos(DLon)));
			OutXi = XiP;
			OutEta = EtaP;
			for (int J = 1; J <= 6; ++J)
			{
				OutXi += S.Alpha[J - 1] * std::sin(2.0 * J * XiP) * std::cosh(2.0 * J * EtaP);
				OutEta += S.Alpha[J - 1] * std::cos(2.0 * J * XiP) * std::sinh(2.0 * J * EtaP);
			}
		}

		/** The value after a "+key=" in a proj4 string, if there. */
		bool ProjValue(const std::string& Proj4, const char* Key, double& Out)
		{
			const std::string Needle = std::string("+") + Key + "=";
			const size_t At = Proj4.find(Needle);
			if (At == std::string::npos) return false;
			const char* Start = Proj4.c_str() + At + Needle.size();
			char* End = nullptr;
			const double V = std::strtod(Start, &End);
			if (End == Start) return false;
			Out = V;
			return true;
		}
	}

	FGeoAnchor::FGeoAnchor(double InLat0Deg, double InLon0Deg)
		: Lat0Deg(InLat0Deg), Lon0Deg(InLon0Deg), bValid(true)
	{
	}

	bool FGeoAnchor::ParseProj4(const std::string& Proj4, FGeoAnchor& Out)
	{
		if (Proj4.find("+proj=tmerc") == std::string::npos) return false;
		if (Proj4.find("+datum=NAD83") == std::string::npos && Proj4.find("+ellps=GRS80") == std::string::npos) return false;
		FGeoAnchor A;
		if (!ProjValue(Proj4, "lat_0", A.Lat0Deg) || !ProjValue(Proj4, "lon_0", A.Lon0Deg)) return false;
		if (!ProjValue(Proj4, "k", A.ScaleK0)) ProjValue(Proj4, "k_0", A.ScaleK0);
		ProjValue(Proj4, "x_0", A.FalseEasting);
		ProjValue(Proj4, "y_0", A.FalseNorthing);
		if (!(A.ScaleK0 > 0.0)) return false;
		A.bValid = true;
		Out = A;
		return true;
	}

	FGeoAnchor FGeoAnchor::ForWorld(const std::string& FileName)
	{
		// The build scripts' centres: build_rayhubbard.py LAT0/LON0 (Rush Creek Yacht Club), build_galveston.py CENTER.
		if (FileName == "RayHubbard") return FGeoAnchor(32.8233, -96.5);
		if (FileName == "GalvestonBay") return FGeoAnchor(29.5446, -95.0193);
		if (FileName == "GulfPassage") return FGeoAnchor(29.33, -94.69);
		if (FileName == "Marseille") return FGeoAnchor(43.295, 5.3625);   // Tools/coast/worlds/Marseille.json "center"
		return FGeoAnchor();
	}

	FMapPoint FGeoAnchor::ToMap(const FLatLon& Geo) const
	{
		const FTmSeries& S = Series();
		double Xi = 0.0;
		double Eta = 0.0;
		ForwardXiEta(Geo.LatDeg * kDegToRad, (Geo.LonDeg - Lon0Deg) * kDegToRad, Xi, Eta);
		double Xi0 = 0.0;
		double Eta0 = 0.0;
		ForwardXiEta(Lat0Deg * kDegToRad, 0.0, Xi0, Eta0);
		const double K = ScaleK0 * S.RectifyingA;
		return { K * (Xi - Xi0) + FalseNorthing, K * Eta + FalseEasting };
	}

	FLatLon FGeoAnchor::ToLatLon(const FMapPoint& Map) const
	{
		const FTmSeries& S = Series();
		double Xi0 = 0.0;
		double Eta0 = 0.0;
		ForwardXiEta(Lat0Deg * kDegToRad, 0.0, Xi0, Eta0);
		const double K = ScaleK0 * S.RectifyingA;
		const double Xi = (Map.North - FalseNorthing) / K + Xi0;
		const double Eta = (Map.East - FalseEasting) / K;
		double XiP = Xi;
		double EtaP = Eta;
		for (int J = 1; J <= 6; ++J)
		{
			XiP -= S.Beta[J - 1] * std::sin(2.0 * J * Xi) * std::cosh(2.0 * J * Eta);
			EtaP -= S.Beta[J - 1] * std::cos(2.0 * J * Xi) * std::sinh(2.0 * J * Eta);
		}
		const double TauP = std::sin(XiP) / std::sqrt(std::sinh(EtaP) * std::sinh(EtaP) + std::cos(XiP) * std::cos(XiP));
		const double DLon = std::atan2(std::sinh(EtaP), std::cos(XiP));
		// Geodetic from conformal latitude: Newton on tau (Karney eq. 19-21), converges in 2-3 steps.
		const double E2 = S.E * S.E;
		double Tau = TauP / (1.0 - E2);
		for (int I = 0; I < 6; ++I)
		{
			const double TauPi = ConformalTan(Tau, S.E);
			const double Slope = (1.0 - E2) * std::sqrt(1.0 + TauPi * TauPi) * std::sqrt(1.0 + Tau * Tau) / (1.0 + (1.0 - E2) * Tau * Tau);
			const double Step = (TauP - TauPi) / Slope;
			Tau += Step;
			if (std::fabs(Step) < 1e-15) break;
		}
		return { std::atan(Tau) / kDegToRad, Lon0Deg + DLon / kDegToRad };
	}

	double FGeoAnchor::Distance(const FMapPoint& A, const FMapPoint& B)
	{
		return std::hypot(A.North - B.North, A.East - B.East);
	}

	int ResolvePlacement(const FGeoAnchor& Anchor, const std::vector<FPlacedThing>& Things, const FGeoPlacement& Placement,
		double SnapMeters, FMapPoint& OutMap, bool& OutMatchedById)
	{
		OutMatchedById = false;
		if (!Placement.Id.empty())
		{
			for (size_t I = 0; I < Things.size(); ++I)
			{
				if (Things[I].Id == Placement.Id)
				{
					OutMatchedById = true;
					OutMap = Things[I].Map;
					return int(I);
				}
			}
		}
		if (!Placement.bHasLatLon || !Anchor.bValid) return -1;
		OutMap = Anchor.ToMap(Placement.Geo);
		int Best = -1;
		double BestDistance = SnapMeters;
		for (size_t I = 0; I < Things.size(); ++I)
		{
			const double D = FGeoAnchor::Distance(Things[I].Map, OutMap);
			if (D <= BestDistance)
			{
				Best = int(I);
				BestDistance = D;
			}
		}
		if (Best >= 0) OutMap = Things[size_t(Best)].Map;
		return Best;
	}
}
