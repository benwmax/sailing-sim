#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Race.h"
#include "RulesCoach.h"
#include "Traffic.h"
#include <random>
#include "TrafficManager.generated.h"

class ASailboatPawn;
class APowerVesselActor;
class UStaticMeshComponent;

/**
 * The other vessels on the water and the races. Spawns the traffic around the player (Settings: Traffic off, light or
 * busy): AI sailboats drawn by ASailboatPawn in traffic mode, runabouts, and on the coast shrimp trawlers, a towboat
 * with barges and ships in the Houston Ship Channel. Steps the simulation (Sailing::FTrafficSim) on the game clock,
 * gives the player's boat the other hulls to bump into, sounds the vessels' whistle signals, coaches the player on
 * the rules (Sailing::FRulesCoach), and runs fleet races (Sailing::FRaceRunner) with a committee boat and marks.
 */
UCLASS()
class SAILINGSIM_API ATrafficManager : public AActor
{
	GENERATED_BODY()

public:
	/** Graphics G4: the fleet for the traffic setting has been placed (the loading screen waits for it). */
	bool IsPopulated() const { return PopulatedLevel >= 0; }
	ATrafficManager();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** 0 off, 1 light, 2 busy. Replaces the traffic (races are kept). */
	void Populate(int32 Level);
	/** A race against Boats AI boats of the player's class, starting in SecondsToStart (300 for the full sequence). */
	void StartRace(int32 Boats, double SecondsToStart);
	void EndRace();
	bool IsRacing() const { return bRace; }

	const Sailing::FTrafficSim& GetSim() const { return Sim; }
	const Sailing::FRaceRunner* GetRace() const { return bRace ? &Race : nullptr; }
	const Sailing::FRulesCoach& GetCoach() const { return Coach; }
	/** What the player has heard or seen lately (signals, give-way actions, race signals), newest last. */
	const TArray<TPair<double, FString>>& GetMessages() const { return Messages; }
	/** The player's place in the race now, by progress around the course (1 = leading), or 0. */
	int32 GetRacePosition() const;

	static ATrafficManager* Find(const UWorld* World);

private:
	int32 AddSailboat(Sailing::EBoatType Type, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const FString& Name);
	int32 AddPower(Sailing::ETrafficKind Kind, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const FString& Name);
	void RemoveVessel(int32 Id);
	void ClearTraffic(bool bKeepRace);
	void UpdateHorns(double Now);
	void Message(const FString& Text);
	FVector2D PlayerPosition() const;
	Sailing::FVesselSnapshot PlayerSnapshot() const;

	Sailing::FTrafficSim Sim;
	Sailing::FRaceRunner Race;
	Sailing::FRulesCoach Coach;
	bool bRace = false;
	bool bRaceLogged = false;
	int32 CommitteeId = -1;
	std::mt19937 Rng{ 2026 };

	UPROPERTY(Transient) TMap<int32, TObjectPtr<ASailboatPawn>> SailActors;
	UPROPERTY(Transient) TMap<int32, TObjectPtr<APowerVesselActor>> PowerActors;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> MarkMeshes;
	TSet<int32> RaceBoats;

	TArray<TPair<double, FString>> Messages;
	size_t EventsSeen = 0;
	double LastEventTime = -1.0;
	int32 SignalsSeen = 0;

	/** Whistle blasts queued: start, end (game seconds), pitch (Hz), loudness (0..1). */
	struct FBlast { double Start, End; float Hz, Level; };
	TArray<FBlast> Blasts;
	double CoachTime = 0.0;
	int32 PopulatedLevel = -1;
	/** Perf 1: the game's clock (unix seconds) for the tidal current, read once a frame on the game thread. */
	double UnixNow = 0.0;
};
