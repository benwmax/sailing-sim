#include "ShipWalk.h"

#include <cstring>
#include <limits>

namespace Sailing
{
	namespace
	{
		constexpr int16_t kNoFloor = -32768;
		constexpr int16_t kOpenOverhead = 32767;

		struct FReader
		{
			const uint8_t* P;
			const uint8_t* End;
			bool bOk = true;

			bool Need(size_t N) { if (!bOk || size_t(End - P) < N) bOk = false; return bOk; }
			template <typename T> T Get()
			{
				T V{};
				if (!Need(sizeof(T))) return V;
				std::memcpy(&V, P, sizeof(T));   // the files and every platform the game runs on are little-endian
				P += sizeof(T);
				return V;
			}
			std::string Text()
			{
				const uint8_t N = Get<uint8_t>();
				if (!Need(N)) return {};
				std::string S(reinterpret_cast<const char*>(P), N);
				P += N;
				return S;
			}
		};

		template <typename T> void Put(std::vector<uint8_t>& Out, T V)
		{
			const size_t At = Out.size();
			Out.resize(At + sizeof(T));
			std::memcpy(Out.data() + At, &V, sizeof(T));
		}
		void PutText(std::vector<uint8_t>& Out, const std::string& S)
		{
			const uint8_t N = uint8_t(std::min<size_t>(S.size(), 255));
			Put<uint8_t>(Out, N);
			Out.insert(Out.end(), S.begin(), S.begin() + N);
		}

		double Wrap180(double Deg)
		{
			Deg = std::fmod(Deg + 180.0, 360.0);
			if (Deg < 0.0) Deg += 360.0;
			return Deg - 180.0;
		}
	}

	// ---- the deck ------------------------------------------------------------------------------------------------

	void FWalkDeck::CellOf(double X, double Y, int& I, int& J) const
	{
		I = int(std::floor((X - X0) / Cell + 0.5));
		J = int(std::floor((Y - Y0) / Cell + 0.5));
	}

	double FWalkDeck::FloorAt(double X, double Y) const
	{
		int I, J;
		CellOf(X, Y, I, J);
		if (!InGrid(I, J)) return std::numeric_limits<double>::quiet_NaN();
		const double F0 = Floor[Index(I, J)];
		if (!std::isfinite(F0)) return F0;
		// Bilinear between the four cells round the point; a corner with no floor, or across a step, takes the nearest's.
		const double Fx = (X - X0) / Cell, Fy = (Y - Y0) / Cell;
		const int I0 = int(std::floor(Fx)), J0 = int(std::floor(Fy));
		const double Tx = Fx - I0, Ty = Fy - J0;
		auto At = [&](int Ii, int Jj)
		{
			if (!InGrid(Ii, Jj)) return F0;
			const double F = Floor[Index(Ii, Jj)];
			return (std::isfinite(F) && std::abs(F - F0) <= FWalkMap::MaxStep) ? F : F0;
		};
		const double A = Lerp(At(I0, J0), At(I0 + 1, J0), Tx);
		const double B = Lerp(At(I0, J0 + 1), At(I0 + 1, J0 + 1), Tx);
		return Lerp(A, B, Ty);
	}

	double FWalkDeck::OverheadAt(double X, double Y) const
	{
		int I, J;
		CellOf(X, Y, I, J);
		if (!InGrid(I, J)) return std::numeric_limits<double>::infinity();
		return Overhead[Index(I, J)];
	}

	bool FWalkDeck::CanStand(double X, double Y) const
	{
		int I, J;
		CellOf(X, Y, I, J);
		return InGrid(I, J) && !Stand.empty() && Stand[Index(I, J)] != 0;
	}

	// ---- the map -------------------------------------------------------------------------------------------------

	int FWalkMap::DeckNamed(const char* Name) const
	{
		for (size_t D = 0; D < Decks.size(); ++D)
		{
			if (Decks[D].Name == Name) return int(D);
		}
		return -1;
	}

	bool FWalkMap::Parse(const uint8_t* Bytes, size_t Size, std::string* Error)
	{
		Decks.clear();
		Links.clear();
		auto Fail = [&](const char* Why)
		{
			if (Error) *Error = Why;
			Decks.clear();
			Links.clear();
			return false;
		};
		if (!Bytes) return Fail("no bytes");
		FReader R{ Bytes, Bytes + Size };
		if (R.Get<uint32_t>() != Magic) return Fail("not a walk file");
		if (R.Get<uint32_t>() != Version) return Fail("unknown walk file version");
		const uint32_t NumDecks = R.Get<uint32_t>(), NumLinks = R.Get<uint32_t>();
		if (!R.bOk || NumDecks == 0 || NumDecks > 32 || NumLinks > 256) return Fail("bad counts");
		Decks.resize(NumDecks);
		for (FWalkDeck& D : Decks)
		{
			D.Name = R.Text();
			D.X0 = R.Get<double>();
			D.Y0 = R.Get<double>();
			D.Cell = R.Get<double>();
			const double BaseZ = R.Get<double>();
			D.NX = R.Get<int32_t>();
			D.NY = R.Get<int32_t>();
			D.AlsoLoad = R.Get<uint32_t>();
			if (!R.bOk || !(D.Cell > 0.005 && D.Cell < 2.0) || D.NX <= 0 || D.NY <= 0 || D.NX > 8192 || D.NY > 4096 || !std::isfinite(BaseZ))
			{
				return Fail("bad deck header");
			}
			const size_t N = size_t(D.NX) * size_t(D.NY);
			if (!R.Need(N * 2 * sizeof(int16_t))) return Fail("deck cut short");
			D.Floor.resize(N);
			D.Overhead.resize(N);
			for (size_t K = 0; K < N; ++K)
			{
				const int16_t V = R.Get<int16_t>();
				D.Floor[K] = V == kNoFloor ? std::numeric_limits<float>::quiet_NaN() : float(BaseZ + V * 0.001);
			}
			for (size_t K = 0; K < N; ++K)
			{
				const int16_t V = R.Get<int16_t>();
				D.Overhead[K] = V == kOpenOverhead ? std::numeric_limits<float>::infinity() : float(BaseZ + V * 0.001);
			}
		}
		Links.resize(NumLinks);
		for (FWalkLink& L : Links)
		{
			L.Kind = EWalkLink(R.Get<uint8_t>());
			L.Lower = R.Get<uint8_t>();
			L.Upper = R.Get<uint8_t>();
			L.Name = R.Text();
			L.Foot.X = R.Get<double>(); L.Foot.Y = R.Get<double>(); L.Foot.Z = R.Get<double>();
			L.Top.X = R.Get<double>(); L.Top.Y = R.Get<double>(); L.Top.Z = R.Get<double>();
			L.HalfWidth = R.Get<double>();
			if (!R.bOk) return Fail("link cut short");
			if (L.Lower >= int(NumDecks) || L.Upper >= int(NumDecks) || L.Lower == L.Upper || L.Kind > EWalkLink::Steps) return Fail("bad link");
			if (!(L.Length() > 0.1)) return Fail("link too short");
		}
		if (R.P != R.End) return Fail("trailing bytes");
		Finish();
		return true;
	}

	std::vector<uint8_t> FWalkMap::Write() const
	{
		std::vector<uint8_t> Out;
		Put<uint32_t>(Out, Magic);
		Put<uint32_t>(Out, Version);
		Put<uint32_t>(Out, uint32_t(Decks.size()));
		Put<uint32_t>(Out, uint32_t(Links.size()));
		for (const FWalkDeck& D : Decks)
		{
			// The base is the lowest floor, so millimetres over it fit an i16 for any deck up to 32 m of rise and headroom.
			double BaseZ = std::numeric_limits<double>::infinity();
			for (float F : D.Floor) if (std::isfinite(F)) BaseZ = std::min(BaseZ, double(F));
			if (!std::isfinite(BaseZ)) BaseZ = 0.0;
			PutText(Out, D.Name);
			Put<double>(Out, D.X0);
			Put<double>(Out, D.Y0);
			Put<double>(Out, D.Cell);
			Put<double>(Out, BaseZ);
			Put<int32_t>(Out, D.NX);
			Put<int32_t>(Out, D.NY);
			Put<uint32_t>(Out, D.AlsoLoad);
			for (float F : D.Floor)
			{
				Put<int16_t>(Out, std::isfinite(F) ? int16_t(Clamp(std::round((F - BaseZ) * 1000.0), -32767.0, 32766.0)) : kNoFloor);
			}
			for (float O : D.Overhead)
			{
				Put<int16_t>(Out, std::isfinite(O) ? int16_t(Clamp(std::round((O - BaseZ) * 1000.0), -32767.0, 32766.0)) : kOpenOverhead);
			}
		}
		for (const FWalkLink& L : Links)
		{
			Put<uint8_t>(Out, uint8_t(L.Kind));
			Put<uint8_t>(Out, uint8_t(L.Lower));
			Put<uint8_t>(Out, uint8_t(L.Upper));
			PutText(Out, L.Name);
			for (double V : { L.Foot.X, L.Foot.Y, L.Foot.Z, L.Top.X, L.Top.Y, L.Top.Z, L.HalfWidth }) Put<double>(Out, V);
		}
		return Out;
	}

	void FWalkMap::Finish()
	{
		for (FWalkDeck& D : Decks)
		{
			const size_t N = size_t(D.NX) * size_t(D.NY);
			D.Stand.assign(N, 0);
			const int R = int(std::ceil(BodyRadius / D.Cell));
			const double R2 = (BodyRadius / D.Cell) * (BodyRadius / D.Cell);
			for (int J = 0; J < D.NY; ++J)
			{
				for (int I = 0; I < D.NX; ++I)
				{
					const float F = D.Floor[D.Index(I, J)];
					if (!std::isfinite(F) || !(D.Overhead[D.Index(I, J)] - F >= MinHeadroom)) continue;
					bool bFits = true;
					for (int Dj = -R; Dj <= R && bFits; ++Dj)
					{
						for (int Di = -R; Di <= R; ++Di)
						{
							if (double(Di * Di + Dj * Dj) > R2) continue;
							if (!D.InGrid(I + Di, J + Dj)) { bFits = false; break; }
							const float G = D.Floor[D.Index(I + Di, J + Dj)];
							if (!std::isfinite(G) || std::abs(G - F) > MaxStep) { bFits = false; break; }
						}
					}
					D.Stand[D.Index(I, J)] = bFits ? 1 : 0;
				}
			}
		}
	}

	// ---- the walker ----------------------------------------------------------------------------------------------

	bool FShipWalker::Reset(const FWalkMap& Map, int InDeck, double X, double Y, double InYawDeg)
	{
		if (InDeck < 0 || InDeck >= int(Map.Decks.size())) return false;
		const FWalkDeck& D = Map.Decks[InDeck];
		int Ci, Cj;
		D.CellOf(X, Y, Ci, Cj);
		const int R = int(std::ceil(2.0 / D.Cell));
		int Bi = -1, Bj = -1;
		double Best = 1e18;
		for (int J = Cj - R; J <= Cj + R; ++J)
		{
			for (int I = Ci - R; I <= Ci + R; ++I)
			{
				if (!D.InGrid(I, J) || !D.Stand[D.Index(I, J)]) continue;
				const double Dx = D.X0 + I * D.Cell - X, Dy = D.Y0 + J * D.Cell - Y;
				const double D2 = Dx * Dx + Dy * Dy;
				if (D2 < Best) { Best = D2; Bi = I; Bj = J; }
			}
		}
		if (Bi < 0) return false;
		Deck = InDeck;
		Link = -1;
		LinkT = 0.0;
		const bool bExact = D.CanStand(X, Y);
		Feet.X = bExact ? X : D.X0 + Bi * D.Cell;
		Feet.Y = bExact ? Y : D.Y0 + Bj * D.Cell;
		Feet.Z = D.FloorAt(Feet.X, Feet.Y);
		Vel = Slide = Vec3();
		YawDeg = Wrap180(InYawDeg);
		PitchDeg = 0.0;
		bSliding = false;
		MountCooldown = 0.0;
		Eye = EyeStand;
		SettleEye(Map, EyeStand, 0.0);
		return true;
	}

	bool FShipWalker::TryMove(const FWalkDeck& D, double Dx, double Dy)
	{
		const double Nx = Feet.X + Dx, Ny = Feet.Y + Dy;
		if (!D.CanStand(Nx, Ny)) return false;
		const double Z = D.FloorAt(Nx, Ny);
		if (!std::isfinite(Z) || std::abs(Z - Feet.Z) > FWalkMap::MaxStep) return false;
		Feet.X = Nx;
		Feet.Y = Ny;
		Feet.Z = Z;
		return true;
	}

	int FShipWalker::LinkInReach(const FWalkMap& Map) const
	{
		if (Link >= 0) return -1;
		for (size_t K = 0; K < Map.Links.size(); ++K)
		{
			const FWalkLink& L = Map.Links[K];
			const Vec3* End = L.Lower == Deck ? &L.Foot : (L.Upper == Deck ? &L.Top : nullptr);
			if (!End) continue;
			const double Dx = End->X - Feet.X, Dy = End->Y - Feet.Y;
			if (Dx * Dx + Dy * Dy < MountRange * MountRange && std::abs(End->Z - Feet.Z) < 0.5) return int(K);
		}
		return -1;
	}

	bool FShipWalker::MountFacing(const FWalkMap& Map, double MoveX, double MoveY, bool bUse)
	{
		if (MountCooldown > 0.0) return false;
		const int K = LinkInReach(Map);
		if (K < 0) return false;
		const FWalkLink& L = Map.Links[K];
		const bool bAtFoot = L.Lower == Deck;
		// Walking onto it: toward the top from the foot, toward the hatch (the foot) from the top.
		Vec3 Dir = bAtFoot ? (L.Top - L.Foot) : (L.Foot - L.Top);
		Dir.Z = 0.0;
		const double DirLen = Dir.LengthXY();
		const double MoveLen = std::sqrt(MoveX * MoveX + MoveY * MoveY);
		bool bWalkOn = false;
		if (DirLen > 0.2 && MoveLen > 0.3)
		{
			// ...and facing it: backing off a ladder's foot, or sidling past its top, never takes it.
			const double Rad = YawDeg * kDegToRad;
			const double Facing = (std::cos(Rad) * Dir.X + std::sin(Rad) * Dir.Y) / DirLen;
			bWalkOn = (MoveX * Dir.X + MoveY * Dir.Y) / (MoveLen * DirLen) > 0.7 && Facing > 0.5;
		}
		if (!bUse && !bWalkOn) return false;
		Link = K;
		LinkT = bAtFoot ? 0.0 : 1.0;
		Feet = bAtFoot ? L.Foot : L.Top;
		Vel = Slide = Vec3();
		bSliding = false;
		return true;
	}

	void FShipWalker::SettleEye(const FWalkMap& Map, double Target, double Dt)
	{
		if (Link >= 0)
		{
			Eye = Dt > 0.0 ? Eye + (EyeStand - Eye) * (1.0 - std::exp(-Dt / EyeTau)) : EyeStand;
			bDucking = false;
			return;
		}
		const FWalkDeck& D = Map.Decks[Deck];
		// Duck before the beam: the lowest overhead under the head and a pace ahead of it.
		const double Rad = YawDeg * kDegToRad;
		const double AheadX = Feet.X + std::cos(Rad) * 0.3, AheadY = Feet.Y + std::sin(Rad) * 0.3;
		const double Here = D.OverheadAt(Feet.X, Feet.Y) - Feet.Z - HeadOverEye;
		// (only a floor's overhead: a gun or the wheel in front of him is in his way, not over his head)
		const double AheadFloor = D.FloorAt(AheadX, AheadY);
		const double Ahead = std::isfinite(AheadFloor) ? D.OverheadAt(AheadX, AheadY) - Feet.Z - HeadOverEye : Here;
		const double Room = std::min(Here, Ahead);
		bDucking = Room < Target;
		const double Want = std::max(EyeLowest, std::min(Target, Room));
		Eye = Dt > 0.0 ? Eye + (Want - Eye) * (1.0 - std::exp(-Dt / EyeTau)) : Want;
		// Never in the beam over him, whatever the easing.
		Eye = std::max(EyeLowest, std::min(Eye, Here));
	}

	void FShipWalker::Step(const FWalkMap& Map, const FWalkInput& In, const Vec3& G, double Dt)
	{
		if (!Map.IsLoaded() || Deck < 0 || Deck >= int(Map.Decks.size())) return;
		Dt = Clamp(Dt, 0.0, 0.1);
		MountCooldown = std::max(0.0, MountCooldown - Dt);
		YawDeg = Wrap180(YawDeg + In.LookYawDeg);
		PitchDeg = Clamp(PitchDeg + In.LookPitchDeg, -80.0, 80.0);

		const double Rad = YawDeg * kDegToRad;
		const double Fx = std::cos(Rad), Fy = std::sin(Rad);
		double Mx = Fx * In.Forward - Fy * In.Right;
		double My = Fy * In.Forward + Fx * In.Right;
		const double MLen = std::sqrt(Mx * Mx + My * My);
		if (MLen > 1.0) { Mx /= MLen; My /= MLen; }

		if (Link >= 0)
		{
			const FWalkLink& L = Map.Links[Link];
			const double Len = std::max(L.Length(), 0.1);
			const double Rate = Clamp(In.Forward, -1.0, 1.0) * ClimbSpeed;
			LinkT += Rate / Len * Dt;
			Vel = (L.Top - L.Foot) * (Rate / Len);
			if (LinkT >= 1.0 || LinkT <= 0.0)
			{
				const bool bTop = LinkT >= 1.0;
				Deck = bTop ? L.Upper : L.Lower;
				Feet = bTop ? L.Top : L.Foot;
				const double Z = Map.Decks[Deck].FloorAt(Feet.X, Feet.Y);
				if (std::isfinite(Z)) Feet.Z = Z;
				Link = -1;
				LinkT = 0.0;
				Vel = Vec3();
				MountCooldown = 0.4;
			}
			else
			{
				Feet = L.Foot + (L.Top - L.Foot) * LinkT;
			}
			SettleEye(Map, EyeStand, Dt);
			return;
		}

		if (MountFacing(Map, Mx, My, In.bUse))
		{
			SettleEye(Map, EyeStand, Dt);
			return;
		}

		const FWalkDeck& D = Map.Decks[Deck];
		double Speed = In.bCrouch ? CrouchSpeed : (In.bRun ? RunSpeed : WalkSpeed);
		if (bDucking) Speed = std::min(Speed, DuckSpeed);
		double Wx = Mx * Speed, Wy = My * Speed;

		// The deck's slope as he feels it: the felt gravity's part along the deck.
		const double GDown = std::max(-G.Z, 0.1);
		const double Gx = G.X, Gy = G.Y, Gp = std::sqrt(Gx * Gx + Gy * Gy);
		if (MLen > 1e-6 && Gp > 1e-6)
		{
			// Downhill (gravity along his way) a little quicker, uphill slower, as a man leans into it.
			const double Along = (Gx * Mx + Gy * My) / (std::sqrt(Mx * Mx + My * My) * GDown);
			const double K = Clamp(1.0 + 1.5 * Along, 0.35, 1.4);
			Wx *= K;
			Wy *= K;
		}
		const double Slope = std::atan2(Gp, GDown);
		const double Grip = GripSlopeDeg * kDegToRad;
		bSliding = Slope > Grip;

		const double Ax = Wx - Vel.X, Ay = Wy - Vel.Y;
		const double ALen = std::sqrt(Ax * Ax + Ay * Ay);
		const double MaxDv = Accel * Dt;
		if (ALen > MaxDv) { Vel.X += Ax / ALen * MaxDv; Vel.Y += Ay / ALen * MaxDv; }
		else { Vel.X = Wx; Vel.Y = Wy; }
		Vel.Z = 0.0;
		// Past the grip his feet go: the slide is its own drift, which his walking can't cancel; it stops on a deck he can
		// stand on again (friction) or against whatever he slides into.
		if (bSliding)
		{
			const double Excess = 1.0 - std::tan(Grip) / std::tan(Slope);
			Slide.X += Gx * Excess * Dt;
			Slide.Y += Gy * Excess * Dt;
			const double SLen = Slide.LengthXY();
			if (SLen > MaxSlide) Slide = Slide * (MaxSlide / SLen);
		}
		else
		{
			const double SLen = Slide.LengthXY();
			Slide = SLen > SlideStop * Dt ? Slide * (1.0 - SlideStop * Dt / SLen) : Vec3();
		}

		// Move in steps of under half a cell so nothing thin is stepped through; slide along whatever stops him.
		const double Dx = (Vel.X + Slide.X) * Dt, Dy = (Vel.Y + Slide.Y) * Dt;
		const int Steps = std::max(1, int(std::ceil(std::sqrt(Dx * Dx + Dy * Dy) / (0.45 * D.Cell))));
		for (int S = 0; S < Steps; ++S)
		{
			const double Sx = Dx / Steps, Sy = Dy / Steps;
			if (TryMove(D, Sx, Sy)) continue;
			const bool bX = Sx != 0.0 && TryMove(D, Sx, 0.0);
			const bool bY = Sy != 0.0 && TryMove(D, 0.0, Sy);
			if (!bX) { Vel.X = 0.0; Slide.X = 0.0; }
			if (!bY) { Vel.Y = 0.0; Slide.Y = 0.0; }
		}

		SettleEye(Map, In.bCrouch ? EyeCrouch : EyeStand, Dt);
	}

	uint32_t FShipWalker::DecksWanted(const FWalkMap& Map, double NearM) const
	{
		if (Deck < 0 || Deck >= int(Map.Decks.size())) return 0;
		uint32_t Want = (1u << Deck) | Map.Decks[Deck].AlsoLoad;
		if (Link >= 0)
		{
			const FWalkLink& L = Map.Links[Link];
			return Want | (1u << L.Lower) | (1u << L.Upper) | Map.Decks[L.Lower].AlsoLoad | Map.Decks[L.Upper].AlsoLoad;
		}
		for (const FWalkLink& L : Map.Links)
		{
			const Vec3* End = L.Lower == Deck ? &L.Foot : (L.Upper == Deck ? &L.Top : nullptr);
			if (!End) continue;
			const double Dx = End->X - Feet.X, Dy = End->Y - Feet.Y;
			if (Dx * Dx + Dy * Dy < NearM * NearM) Want |= 1u << (L.Lower == Deck ? L.Upper : L.Lower);
		}
		return Want;
	}
}
