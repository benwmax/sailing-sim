#include "LakeTerrain.h"
#include <cmath>
#include <cstring>

namespace Sailing
{
	namespace
	{
		template <typename T>
		T ReadLE(const uint8_t* P) { T V; std::memcpy(&V, P, sizeof(T)); return V; }
	}

	double FTerrainTile::HeightAt(double X, double Y) const
	{
		const double R = Clamp((X - OriginX) / Cell, 0.0, double(Cells)), C = Clamp((Y - OriginY) / Cell, 0.0, double(Cells));
		const int R0 = std::min(int(R), Cells - 1), C0 = std::min(int(C), Cells - 1);
		const double FR = R - R0, FC = C - C0;
		return Lerp(Lerp(Node(R0, C0), Node(R0, C0 + 1), FC), Lerp(Node(R0 + 1, C0), Node(R0 + 1, C0 + 1), FC), FR);
	}

	FTileSet::FTileSet(double InTileM, double InOriginX, double InOriginY, const std::vector<std::shared_ptr<const FTerrainTile>>& InTiles)
		: TileM(InTileM), OriginX(InOriginX), OriginY(InOriginY)
	{
		int RMin = 0, RMax = -1, CMin = 0, CMax = -1;
		double Fine = 1e9;
		for (const std::shared_ptr<const FTerrainTile>& T : InTiles)
		{
			if (!T) continue;
			if (Count == 0) { RMin = RMax = T->Row; CMin = CMax = T->Col; }
			RMin = std::min(RMin, T->Row); RMax = std::max(RMax, T->Row);
			CMin = std::min(CMin, T->Col); CMax = std::max(CMax, T->Col);
			Fine = std::min(Fine, T->Cell);
			++Count;
		}
		if (Count == 0) return;
		Finest = Fine;
		R0 = RMin; C0 = CMin; NR = RMax - RMin + 1; NC = CMax - CMin + 1;
		Slots.assign(size_t(NR) * NC, nullptr);
		for (const std::shared_ptr<const FTerrainTile>& T : InTiles)
			if (T) Slots[size_t(T->Row - R0) * NC + (T->Col - C0)] = T;
	}

	const FTerrainTile* FTileSet::At(double X, double Y) const
	{
		if (Count == 0) return nullptr;
		const int R = int(std::floor((X - OriginX) / TileM)) - R0, C = int(std::floor((Y - OriginY) / TileM)) - C0;
		if (R < 0 || C < 0 || R >= NR || C >= NC) return nullptr;
		return Slots[size_t(R) * NC + C].get();
	}

	bool FLakeTerrain::LoadHeight(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 4;
		if (Size < Header || std::memcmp(Data, "SSHT", 4) != 0) return false;
		const uint32_t Version = ReadLE<uint32_t>(Data + 4);
		const int NX = int(ReadLE<uint32_t>(Data + 8));
		const int NY = int(ReadLE<uint32_t>(Data + 12));
		if (Version != 1 || NX <= 1 || NY <= 1 || Size < Header + size_t(NX) * NY * 2) return false;
		Cell = ReadLE<float>(Data + 16);
		GridOriginX = OriginX = ReadLE<float>(Data + 20);
		GridOriginY = OriginY = ReadLE<float>(Data + 24);
		Unit = ReadLE<float>(Data + 28);
		GridRows = Rows = NY;
		GridCols = Cols = NX;
		RowOff = ColOff = 0;
		auto Grid = std::make_shared<std::vector<int16_t>>(size_t(NX) * NY);
		std::memcpy(Grid->data(), Data + Header, Grid->size() * 2);
		Heights = Grid;
		Tiles.reset();
		return true;
	}

	bool FLakeTerrain::LoadTrees(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 3;
		if (Size < Header || std::memcmp(Data, "SSTR", 4) != 0) return false;
		auto T = std::make_shared<FTrees>();
		T->Cols = int(ReadLE<uint32_t>(Data + 8));
		T->Rows = int(ReadLE<uint32_t>(Data + 12));
		T->Cell = ReadLE<float>(Data + 16);
		T->OriginX = ReadLE<float>(Data + 20);
		T->OriginY = ReadLE<float>(Data + 24);
		if (Size < Header + size_t(T->Rows) * T->Cols) { Trees.reset(); return false; }
		T->Density.assign(Data + Header, Data + Header + size_t(T->Rows) * T->Cols);
		Trees = T;
		return true;
	}

	bool FLakeTerrain::LoadDetail(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 4;
		if (Size < Header || std::memcmp(Data, "SSDT", 4) != 0 || ReadLE<uint32_t>(Data + 4) != 1 || Rows == 0) return false;
		const int Tile = int(ReadLE<uint32_t>(Data + 8));
		const size_t Count = ReadLE<uint32_t>(Data + 12);
		const size_t Nodes = size_t(Tile + 1) * (Tile + 1);
		if (Tile < 2 || Size < Header + Count * (8 + Nodes * 2)) return false;
		auto D = std::make_shared<FDetail>();
		D->Tile = Tile;
		D->Cell = ReadLE<float>(Data + 16);
		D->OriginX = ReadLE<float>(Data + 20);
		D->OriginY = ReadLE<float>(Data + 24);
		D->Unit = ReadLE<float>(Data + 28);
		const double Span = Tile * D->Cell;
		D->Rows = int(std::ceil((OriginX + (Rows - 1) * Cell - D->OriginX) / Span)) + 1;
		D->Cols = int(std::ceil((OriginY + (Cols - 1) * Cell - D->OriginY) / Span)) + 1;
		D->Index.assign(size_t(D->Rows) * D->Cols, -1);
		const uint8_t* P = Data + Header;
		for (size_t K = 0; K < Count; ++K)
		{
			const int R = ReadLE<int32_t>(P + 8 * K), C = ReadLE<int32_t>(P + 8 * K + 4);
			if (R >= 0 && C >= 0 && R < D->Rows && C < D->Cols) D->Index[size_t(R) * D->Cols + C] = int32_t(K);
		}
		D->Heights.resize(Count * Nodes);
		std::memcpy(D->Heights.data(), P + 8 * Count, D->Heights.size() * 2);
		Detail = D;
		return true;
	}

	int FLakeTerrain::DetailTileAt(double X, double Y, double& U, double& V) const
	{
		if (!Detail) return -1;
		const FDetail& D = *Detail;
		const double Span = D.Tile * D.Cell;
		const double TX = (X - D.OriginX) / Span, TY = (Y - D.OriginY) / Span;
		if (TX < 0.0 || TY < 0.0) return -1;
		const int R = int(TX), C = int(TY);
		if (R >= D.Rows || C >= D.Cols) return -1;
		U = (TX - R) * D.Tile;
		V = (TY - C) * D.Tile;
		return D.Index[size_t(R) * D.Cols + C];
	}

	bool FLakeTerrain::DetailHeightAt(double X, double Y, double& Height) const
	{
		double U, V;
		const int Index = DetailTileAt(X, Y, U, V);
		if (Index < 0) return false;
		const FDetail& D = *Detail;
		const int N = D.Tile + 1;
		const int R0 = int(U) < D.Tile ? int(U) : D.Tile - 1, C0 = int(V) < D.Tile ? int(V) : D.Tile - 1;
		const double FR = U - R0, FC = V - C0;
		const int16_t* T = D.Heights.data() + size_t(Index) * N * N;
		const double H00 = T[R0 * N + C0], H01 = T[R0 * N + C0 + 1], H10 = T[(R0 + 1) * N + C0], H11 = T[(R0 + 1) * N + C0 + 1];
		Height = Lerp(Lerp(H00, H01, FC), Lerp(H10, H11, FC), FR) * D.Unit + LevelBelowPool;
		return true;
	}

	bool FLakeTerrain::HasDetailIn(double MinX, double MinY, double MaxX, double MaxY) const
	{
		if (!Detail) return false;
		const FDetail& D = *Detail;
		const double Span = D.Tile * D.Cell;
		const int R0 = int(std::floor((MinX - D.OriginX) / Span)), R1 = int(std::floor((MaxX - D.OriginX) / Span));
		const int C0 = int(std::floor((MinY - D.OriginY) / Span)), C1 = int(std::floor((MaxY - D.OriginY) / Span));
		for (int R = R0 < 0 ? 0 : R0; R <= R1 && R < D.Rows; ++R)
			for (int C = C0 < 0 ? 0 : C0; C <= C1 && C < D.Cols; ++C)
				if (D.Index[size_t(R) * D.Cols + C] >= 0) return true;
		return false;
	}

	void FLakeTerrain::InitSyntheticTrees(int InRows, int InCols, double InCell, double InOriginX, double InOriginY, const std::vector<uint8_t>& Density)
	{
		auto T = std::make_shared<FTrees>();
		T->Rows = InRows;
		T->Cols = InCols;
		T->Cell = InCell;
		T->OriginX = InOriginX;
		T->OriginY = InOriginY;
		T->Density = Density;
		T->Density.resize(size_t(T->Rows) * T->Cols, 0);
		Trees = T;
	}

	void FLakeTerrain::InitSynthetic(int InRows, int InCols, double InCell, double InOriginX, double InOriginY, const std::vector<float>& InHeights)
	{
		GridRows = Rows = InRows;
		GridCols = Cols = InCols;
		Cell = InCell;
		GridOriginX = OriginX = InOriginX;
		GridOriginY = OriginY = InOriginY;
		RowOff = ColOff = 0;
		Unit = 0.01;
		auto Grid = std::make_shared<std::vector<int16_t>>(size_t(Rows) * Cols);
		for (size_t I = 0; I < Grid->size(); ++I)
		{
			(*Grid)[I] = int16_t(Clamp(std::round(InHeights[I] / Unit), -32000.0, 32000.0));
		}
		Heights = Grid;
		Tiles.reset();
	}

	void FLakeTerrain::SetTiles(std::shared_ptr<const FTileSet> InTiles, double FinestCell)
	{
		Heights.reset();
		GridRows = GridCols = RowOff = ColOff = 0;
		Tiles = std::move(InTiles);
		if (!Tiles || Tiles->Num() == 0) { Rows = Cols = 0; return; }
		Cell = FinestCell > 0.0 ? FinestCell : Tiles->GetFinestCell();
		OriginX = Tiles->GetOriginX() + Tiles->GetRow0() * Tiles->GetTileM();
		OriginY = Tiles->GetOriginY() + Tiles->GetCol0() * Tiles->GetTileM();
		Rows = int(std::lround(Tiles->GetNumRows() * Tiles->GetTileM() / Cell)) + 1;
		Cols = int(std::lround(Tiles->GetNumCols() * Tiles->GetTileM() / Cell)) + 1;
	}

	FLakeTerrain FLakeTerrain::WindowAround(double X, double Y, double HalfM) const
	{
		FLakeTerrain W = *this;
		if (Rows == 0) return W;
		// Node range of the window within the view, snapped to the spacing.
		const int RA = std::max(0, int(std::floor((X - HalfM - OriginX) / Cell))), RB = std::min(Rows - 1, int(std::ceil((X + HalfM - OriginX) / Cell)));
		const int CA = std::max(0, int(std::floor((Y - HalfM - OriginY) / Cell))), CB = std::min(Cols - 1, int(std::ceil((Y + HalfM - OriginY) / Cell)));
		if (RB <= RA || CB <= CA) { W.Rows = W.Cols = 0; return W; }
		W.OriginX = OriginX + RA * Cell;
		W.OriginY = OriginY + CA * Cell;
		W.Rows = RB - RA + 1;
		W.Cols = CB - CA + 1;
		W.RowOff = RowOff + RA;
		W.ColOff = ColOff + CA;
		return W;
	}

	double FLakeTerrain::GridNode(int Row, int Col) const
	{
		// Whole grid: a node of the data, clamped to its edge.
		Row = Row < 0 ? 0 : (Row >= GridRows ? GridRows - 1 : Row);
		Col = Col < 0 ? 0 : (Col >= GridCols ? GridCols - 1 : Col);
		return (*Heights)[size_t(Row) * GridCols + Col] * Unit;
	}

	double FLakeTerrain::NodeHeight(int Row, int Col) const
	{
		Row = Row < 0 ? 0 : (Row >= Rows ? Rows - 1 : Row);
		Col = Col < 0 ? 0 : (Col >= Cols ? Cols - 1 : Col);
		if (Heights) return GridNode(Row + RowOff, Col + ColOff) + LevelBelowPool;
		if (!Tiles) return 50.0;
		const double X = OriginX + Row * Cell, Y = OriginY + Col * Cell;
		const FTerrainTile* T = Tiles->At(X, Y);
		return (T ? T->HeightAt(X, Y) : 50.0) + LevelBelowPool;
	}

	double FLakeTerrain::GroundAt(double X, double Y) const
	{
		if (Tiles)
		{
			const FTerrainTile* T = Tiles->At(X, Y);
			return T ? T->HeightAt(X, Y) + LevelBelowPool : 50.0; // nothing resident (or no data): land
		}
		const double R = (X - GridOriginX) / Cell, C = (Y - GridOriginY) / Cell;
		if (R < -1.0 || C < -1.0 || R > GridRows || C > GridCols) return 50.0; // off the map: land
		const int R0 = int(std::floor(R)), C0 = int(std::floor(C));
		const double FR = R - R0, FC = C - C0;
		const double H00 = GridNode(R0, C0), H01 = GridNode(R0, C0 + 1), H10 = GridNode(R0 + 1, C0), H11 = GridNode(R0 + 1, C0 + 1);
		return Lerp(Lerp(H00, H01, FC), Lerp(H10, H11, FC), FR) + LevelBelowPool;
	}

	double FLakeTerrain::HeightAt(double X, double Y) const
	{
		if (Rows == 0 && !Heights && !Tiles) return -1000.0; // no terrain: open water everywhere
		double Fine;
		if (DetailHeightAt(X, Y, Fine)) return Fine;
		return GroundAt(X, Y);
	}

	double FLakeTerrain::CanopyAt(double X, double Y) const
	{
		if (!Trees || Trees->Rows == 0) return 0.0;
		const FTrees& T = *Trees;
		const int R = int((X - T.OriginX) / T.Cell), C = int((Y - T.OriginY) / T.Cell);
		if (R < 0 || C < 0 || R >= T.Rows || C >= T.Cols) return 0.0;
		return T.Density[size_t(R) * T.Cols + C] / 255.0 * 12.0;
	}

	double FLakeTerrain::FetchToward(double X, double Y, double FromRadians, double MaxDistance) const
	{
		if (Rows == 0 && !Heights && !Tiles) return MaxDistance;
		const double DX = std::cos(FromRadians), DY = std::sin(FromRadians);
		const double Step = Cell;
		for (double S = Step; S < MaxDistance; S += Step)
		{
			if (HeightAt(X + DX * S, Y + DY * S) > 0.0) return S;
		}
		return MaxDistance;
	}

	double FLakeTerrain::EffectiveFetch(double X, double Y, double FromRadians, double MaxDistance) const
	{
		// SWAN over Ray Hubbard (W3): at Rush Creek in a northerly the single ray finds 135 m and 4 cm of chop where SWAN
		// has 13 cm, grown down the lake and arriving at an angle. Saville's effective fetch (Saville, McClendon and Cochran
		// 1962; the Shore Protection Manual's method): rays every 11.25 deg to +/-45 deg, sum(F cos^2 a) / sum(cos a), the
		// wind's stress along each ray (cos a) times its waves' share toward the point (cos a).
		double Sum = 0.0, Weights = 0.0;
		for (int K = -4; K <= 4; ++K)
		{
			const double A = K * (kPi / 16.0), W = std::cos(A);
			Sum += W * W * FetchToward(X, Y, FromRadians + A, MaxDistance);
			Weights += W;
		}
		return Sum / Weights;
	}

	double FShelterMap::LeeDeficit(double Ratio)
	{
		// Shelterbelt and escarpment wakes: deepest within about 4 heights, still a quarter down at 20, gone by 30.
		return 0.62 * (1.0 - SmoothStep(4.0, 30.0, Ratio));
	}

	double FShelterMap::OpenWaterBuild(double FetchMeters)
	{
		// The internal boundary layer from a land-water roughness step. W6's LES of Ray Hubbard's outline (a hot afternoon,
		// docs/water-6/les-pilot.md): over the water downwind of the first shore the 12.5 m wind is 1.07 of the land's mean
		// within 250 m, 1.11 at 250-500 m and 1.13 from 0.5 to 2 km. As a fraction of that open-water value: 0.91 at the
		// shore, 97% by 250 m, full by about a kilometre (e-folding 230 m). (The LES eases to 1.06 beyond 4 km, where its
		// periodic tile feeds the far shore's land back in: not modelled.)
		return 1.0 - 0.09 * std::exp(-std::max(FetchMeters, 0.0) / 230.0);
	}

	double FShelterMap::OpenWaterGust(double FetchMeters)
	{
		// The same LES: gust intensity (std / mean at a point) 0.15 within a kilometre of the upwind shore, 0.14 at 1-2 km,
		// 0.13 at 2-4 km and 0.11 beyond (0.18 over the land beside it): the land's eddies decay over the smooth, unheated
		// water. The stations that calibrate the gusts (WindClimate.h) are on land at the shore, so they are the 1 here.
		// Through the bands' centres, flat beyond (the 4-10 km band's 0.11 taken at 7 km).
		constexpr double F[] = { 750.0, 1500.0, 3000.0, 7000.0 }, G[] = { 0.15, 0.14, 0.13, 0.11 };
		if (FetchMeters <= F[0]) return 1.0;
		for (int I = 1; I < 4; ++I)
		{
			if (FetchMeters <= F[I]) return Lerp(G[I - 1], G[I], (FetchMeters - F[I - 1]) / (F[I] - F[I - 1])) / G[0];
		}
		return G[3] / G[0];
	}

	void FShelterMap::Build(const FLakeTerrain& Terrain, double InFromRadians, double InCell, const std::vector<FShelterObstacle>* Obstacles)
	{
		FromRadians = InFromRadians;
		Cell = InCell;
		if (!Terrain.IsValid()) { Rows = Cols = 0; Lee.clear(); Building.clear(); Gust.clear(); return; }
		OriginX = Terrain.GetOriginX();
		OriginY = Terrain.GetOriginY();
		Rows = int(Terrain.GetRows() * Terrain.GetCell() / Cell) + 1;
		Cols = int(Terrain.GetCols() * Terrain.GetCell() / Cell) + 1;
		Lee.assign(size_t(Rows) * Cols, 1.0f);
		Building.assign(size_t(Rows) * Cols, 1.0f);
		Gust.assign(size_t(Rows) * Cols, 1.0f);
		constexpr double kMaxFetch = 7000.0;
		// Houses (and anything else) rasterised to the march's resolution: the highest top in each 20 m cell.
		constexpr double Step = 20.0;
		const int HRows = int(Rows * Cell / Step) + 2, HCols = int(Cols * Cell / Step) + 2;
		std::vector<float> Extra;
		if (Obstacles && !Obstacles->empty())
		{
			Extra.assign(size_t(HRows) * HCols, 0.0f);
			for (const FShelterObstacle& O : *Obstacles)
			{
				const int R0 = int(std::floor((O.X - O.Radius - OriginX) / Step)), R1 = int(std::floor((O.X + O.Radius - OriginX) / Step));
				const int C0 = int(std::floor((O.Y - O.Radius - OriginY) / Step)), C1 = int(std::floor((O.Y + O.Radius - OriginY) / Step));
				for (int R = std::max(R0, 0); R <= std::min(R1, HRows - 1); ++R)
					for (int C = std::max(C0, 0); C <= std::min(C1, HCols - 1); ++C)
						Extra[size_t(R) * HCols + C] = std::max(Extra[size_t(R) * HCols + C], float(O.Top));
			}
		}
		auto ExtraAt = [&](double X, double Y)
		{
			if (Extra.empty()) return 0.0;
			const int R = int(std::floor((X - OriginX) / Step)), C = int(std::floor((Y - OriginY) / Step));
			return R < 0 || C < 0 || R >= HRows || C >= HCols ? 0.0 : double(Extra[size_t(R) * HCols + C]);
		};
		const double DX = std::cos(FromRadians), DY = std::sin(FromRadians);
		for (int R = 0; R < Rows; ++R)
		{
			for (int C = 0; C < Cols; ++C)
			{
				const double X = OriginX + R * Cell, Y = OriginY + C * Cell;
				if (Terrain.HeightAt(X, Y) > 0.0) continue; // only water matters
				// Upwind: the lee of anything within 30 heights (a 30 m bluff with its trees reaches 900 m), and the first land
				// (to 7 km: the gusts ease that far out).
				double Reduction = 0.0, Fetch = -1.0;
				const double MaxX = OriginX + Terrain.GetRows() * Terrain.GetCell(), MaxY = OriginY + Terrain.GetCols() * Terrain.GetCell();
				for (double S = Step; S <= kMaxFetch; S += (S < 1000.0 ? Step : 2.0 * Step))
				{
					const double PX = X + DX * S, PY = Y + DY * S;
					// Past the edge of the bake: nothing more is known (its "high land" is a stand-in, not a hill).
					if (PX < OriginX || PY < OriginY || PX > MaxX || PY > MaxY)
					{
						if (Fetch < 0.0) Fetch = S;
						break;
					}
					const double Ground = Terrain.HeightAt(PX, PY);
					if (Ground > 0.0 && Fetch < 0.0) Fetch = S;
					if (S > 1000.0)
					{
						if (Fetch >= 0.0) break;
						continue;
					}
					const double Top = std::max({ Ground, 0.0, ExtraAt(PX, PY) }) + (Ground > 0.0 ? Terrain.CanopyAt(PX, PY) : 0.0);
					if (Top < 1.0) continue;
					Reduction = std::max(Reduction, LeeDeficit(S / Top));
				}
				Lee[size_t(R) * Cols + C] = float(1.0 - Reduction);
				Building[size_t(R) * Cols + C] = float(OpenWaterBuild(Fetch < 0.0 ? 1e9 : Fetch));
				Gust[size_t(R) * Cols + C] = float(OpenWaterGust(Fetch < 0.0 ? 1e9 : Fetch));
			}
		}
	}

	double FShelterMap::Sample(const std::vector<float>& Grid, double X, double Y) const
	{
		if (Rows == 0) return 1.0;
		const double R = (X - OriginX) / Cell, C = (Y - OriginY) / Cell;
		const int R0 = int(std::floor(R)), C0 = int(std::floor(C));
		if (R0 < 0 || C0 < 0 || R0 + 1 >= Rows || C0 + 1 >= Cols) return 1.0;
		const double FR = R - R0, FC = C - C0;
		auto F = [&](int RR, int CC) { return double(Grid[size_t(RR) * Cols + CC]); };
		return Lerp(Lerp(F(R0, C0), F(R0, C0 + 1), FC), Lerp(F(R0 + 1, C0), F(R0 + 1, C0 + 1), FC), FR);
	}

	double FShelterMap::FactorAt(double X, double Y) const
	{
		return LeeAt(X, Y) * BuildAt(X, Y);
	}
}
