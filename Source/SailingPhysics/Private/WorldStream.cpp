#include "WorldStream.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace Sailing
{
	namespace
	{
		template <typename T>
		T ReadValue(const uint8_t* P) { T V; std::memcpy(&V, P, sizeof(T)); return V; }
	}

	size_t FTileIndex::HeaderSize(const uint8_t* Data, size_t Size)
	{
		if (Size < kHeaderBytes || std::memcmp(Data, "SSTI", 4) != 0 || ReadValue<uint32_t>(Data + 4) != 1) return 0;
		return kHeaderBytes + size_t(ReadValue<uint32_t>(Data + 8)) * kEntryBytes;
	}

	bool FTileIndex::Parse(const uint8_t* Data, size_t Size)
	{
		const size_t Need = HeaderSize(Data, Size);
		if (Need == 0 || Size < Need) return false;
		const uint32_t Count = ReadValue<uint32_t>(Data + 8);
		TileM = ReadValue<float>(Data + 12);
		OriginX = ReadValue<double>(Data + 16);
		OriginY = ReadValue<double>(Data + 24);
		Finest = ReadValue<float>(Data + 32);
		if (!(TileM > 0.0) || !(Finest > 0.0)) return false;
		Tiles.clear();
		Tiles.reserve(Count);
		for (uint32_t K = 0; K < Count; ++K)
		{
			const uint8_t* P = Data + kHeaderBytes + size_t(K) * kEntryBytes;
			FTileEntry T;
			T.Row = ReadValue<int32_t>(P);
			T.Col = ReadValue<int32_t>(P + 4);
			T.Cells = int(ReadValue<uint32_t>(P + 8));
			T.Cell = ReadValue<float>(P + 12);
			T.Unit = ReadValue<float>(P + 16);
			T.Flags = ReadValue<uint32_t>(P + 20);
			T.MinHeight = ReadValue<int16_t>(P + 24);
			T.MaxHeight = ReadValue<int16_t>(P + 26);
			T.Offset = ReadValue<uint64_t>(P + 28);
			T.StoredSize = ReadValue<uint32_t>(P + 36);
			if (T.Cells < 1 || !(T.Cell > 0.0) || std::fabs(T.Cells * T.Cell - TileM) > 1e-3 * TileM) return false;
			Tiles.push_back(T);
		}
		bStreamed = true;
		Reindex();
		return true;
	}

	FTileIndex FTileIndex::ForGrid(const FLakeTerrain& Terrain, double InTileM)
	{
		FTileIndex I;
		if (!Terrain.IsValid()) return I;
		const double Cell = Terrain.GetCell();
		// A whole number of cells per tile (the lake's 5 m: 1280; the bay's 10 m: 640; the Gulf's 50 m: 128).
		const int Cells = std::max(1, int(std::lround(InTileM / Cell)));
		I.TileM = Cells * Cell;
		I.OriginX = Terrain.GetOriginX();
		I.OriginY = Terrain.GetOriginY();
		I.Finest = Cell;
		const int NR = (Terrain.GetRows() - 1 + Cells - 1) / Cells, NC = (Terrain.GetCols() - 1 + Cells - 1) / Cells;
		for (int R = 0; R < NR; ++R)
			for (int C = 0; C < NC; ++C)
			{
				FTileEntry T;
				T.Row = R;
				T.Col = C;
				T.Cells = Cells;
				T.Cell = Cell;
				I.Tiles.push_back(T);
			}
		I.Reindex();
		return I;
	}

	void FTileIndex::Reindex()
	{
		ByCell.clear();
		for (size_t K = 0; K < Tiles.size(); ++K) ByCell[Key(Tiles[K].Row, Tiles[K].Col)] = int(K);
	}

	int FTileIndex::Find(int Row, int Col) const
	{
		const auto It = ByCell.find(Key(Row, Col));
		return It == ByCell.end() ? -1 : It->second;
	}

	void FTileIndex::TileOf(double X, double Y, int& Row, int& Col) const
	{
		Row = int(std::floor((X - OriginX) / TileM));
		Col = int(std::floor((Y - OriginY) / TileM));
	}

	double FTileIndex::DistanceTo(const FTileEntry& T, double X, double Y) const
	{
		double X0, Y0;
		Corner(T, X0, Y0);
		const double DX = std::max({ X0 - X, 0.0, X - (X0 + TileM) }), DY = std::max({ Y0 - Y, 0.0, Y - (Y0 + TileM) });
		return std::sqrt(DX * DX + DY * DY);
	}

	void FTileIndex::Bounds(double& MinX, double& MinY, double& MaxX, double& MaxY) const
	{
		MinX = MinY = 1e300;
		MaxX = MaxY = -1e300;
		for (const FTileEntry& T : Tiles)
		{
			double X0, Y0;
			Corner(T, X0, Y0);
			MinX = std::min(MinX, X0); MinY = std::min(MinY, Y0);
			MaxX = std::max(MaxX, X0 + TileM); MaxY = std::max(MaxY, Y0 + TileM);
		}
	}

	std::shared_ptr<const FTerrainTile> FTileIndex::MakeTile(const FTileEntry& T, const uint8_t* Raw, size_t Size) const
	{
		const size_t Nodes = size_t(T.Cells + 1) * (T.Cells + 1);
		if (!Raw || Size < Nodes * 2) return nullptr;
		auto Tile = std::make_shared<FTerrainTile>();
		Tile->Row = T.Row;
		Tile->Col = T.Col;
		Tile->Cells = T.Cells;
		Tile->Cell = T.Cell;
		Tile->Unit = T.Unit;
		Corner(T, Tile->OriginX, Tile->OriginY);
		Tile->Heights.resize(Nodes);
		std::memcpy(Tile->Heights.data(), Raw, Nodes * 2);
		return Tile;
	}

	std::shared_ptr<const FTerrainTile> FTileIndex::CutTile(const FTileEntry& T, const FLakeTerrain& Grid) const
	{
		auto Tile = std::make_shared<FTerrainTile>();
		Tile->Row = T.Row;
		Tile->Col = T.Col;
		Tile->Cells = T.Cells;
		Tile->Cell = T.Cell;
		Tile->Unit = 0.01;
		Corner(T, Tile->OriginX, Tile->OriginY);
		const int N = T.Cells + 1;
		Tile->Heights.resize(size_t(N) * N);
		// The grid's own nodes (clamped at its edge, as NodeHeight does), without the water level: the tile holds the data.
		const double Level = Grid.GetLevelBelowPool();
		for (int R = 0; R < N; ++R)
			for (int C = 0; C < N; ++C)
			{
				const double H = Grid.NodeHeight(T.Row * T.Cells + R, T.Col * T.Cells + C) - Level;
				Tile->Heights[size_t(R) * N + C] = int16_t(Clamp(std::round(H / Tile->Unit), -32000.0, 32000.0));
			}
		return Tile;
	}

	void PlanStreaming(const FTileIndex& Index, double X, double Y, const FStreamRadii& Radii,
		const std::vector<uint8_t>& Resident, const std::vector<uint8_t>& InFlight, std::vector<int>& OutLoad, std::vector<int>& OutDrop)
	{
		OutLoad.clear();
		OutDrop.clear();
		const std::vector<FTileEntry>& Tiles = Index.GetTiles();
		std::vector<std::pair<double, int>> Wanted;
		for (int K = 0; K < int(Tiles.size()); ++K)
		{
			const double D = Index.DistanceTo(Tiles[K], X, Y);
			const bool bResident = K < int(Resident.size()) && Resident[K];
			const bool bFlying = K < int(InFlight.size()) && InFlight[K];
			if (bResident && D > Radii.KeepM) OutDrop.push_back(K);
			else if (!bResident && !bFlying && D <= Radii.LoadM) Wanted.push_back({ D, K });
		}
		std::sort(Wanted.begin(), Wanted.end());
		for (const std::pair<double, int>& W : Wanted) OutLoad.push_back(W.second);
	}

	bool NeedsRecentre(double OriginX, double OriginY, double X, double Y, double& OutX, double& OutY, double ThresholdM, double LatticeM)
	{
		OutX = OriginX;
		OutY = OriginY;
		const double DX = X - OriginX, DY = Y - OriginY;
		if (DX * DX + DY * DY <= ThresholdM * ThresholdM) return false;
		OutX = std::round(X / LatticeM) * LatticeM;
		OutY = std::round(Y / LatticeM) * LatticeM;
		return OutX != OriginX || OutY != OriginY;
	}

	bool FPhysicsWindow::Contains(double X, double Y) const
	{
		return bValid && std::fabs(X - CenterX) <= CoreM && std::fabs(Y - CenterY) <= CoreM;
	}
}
