#include "PowerVesselActor.h"
#include "SailingSim.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

using namespace Sailing;

namespace
{
	const FLinearColor White(0.9f, 0.9f, 0.88f), Dark(0.05f, 0.05f, 0.06f), Steel(0.35f, 0.36f, 0.38f);
	const FLinearColor NavRed(1.f, 0.04f, 0.03f), NavGreen(0.05f, 1.f, 0.2f), NavWhite(1.f, 0.95f, 0.85f);
	constexpr float Masthead[2] = { -112.5f, 112.5f };
	// Sidelights show from right ahead, cutting off within 1 to 3 degrees across the bow (Annex I, 9(a)): both are
	// seen from dead ahead.
	constexpr float Starboard[2] = { -2.f, 112.5f };
	constexpr float Port[2] = { -112.5f, 2.f };
	constexpr float AllRound[2] = { -180.f, 180.f };
}

APowerVesselActor::APowerVesselActor()
{
	PrimaryActorTick.bCanEverTick = false; // the traffic manager moves her
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(TEXT("/Engine/BasicShapes/Cone.Cone"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Basic(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Emissive(TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	Cube = CubeMesh.Object;
	Cylinder = CylinderMesh.Object;
	Cone = ConeMesh.Object;
	Sphere = SphereMesh.Object;
	ShapeMaterial = Basic.Object;
	EmissiveMaterial = Emissive.Object;
}

UStaticMeshComponent* APowerVesselActor::Part(UStaticMesh* Mesh, const FVector& LocationM, const FVector& SizeM, const FLinearColor& Color, const FRotator& Rotation)
{
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
	C->SetupAttachment(Root);
	C->SetStaticMesh(Mesh);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetRelativeLocation(LocationM * 100.0);
	C->SetRelativeRotation(Rotation);
	C->SetRelativeScale3D(SizeM); // basic shapes are 1 m across
	C->RegisterComponent();
	if (UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this))
	{
		Mid->SetVectorParameterValue(TEXT("Color"), Color);
		C->SetMaterial(0, Mid);
	}
	Parts.Add(C);
	return C;
}

void APowerVesselActor::Light(const FVector& LocationM, const FLinearColor& Color, float ArcFrom, float ArcTo)
{
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
	C->SetupAttachment(Root);
	C->SetStaticMesh(Sphere);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetCastShadow(false);
	C->SetRelativeLocation(LocationM * 100.0);
	C->SetRelativeScale3D(FVector(0.2f));
	C->RegisterComponent();
	if (UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(EmissiveMaterial, this))
	{
		Mid->SetVectorParameterValue(TEXT("Color"), Color);
		Mid->SetScalarParameterValue(TEXT("Intensity"), 200.f);
		C->SetMaterial(0, Mid);
	}
	C->SetVisibility(false);
	FNavLight L;
	L.Mesh = C;
	L.Local = LocationM;
	L.ArcFrom = ArcFrom;
	L.ArcTo = ArcTo;
	Lights.Add(L);
	Parts.Add(C);
}

void APowerVesselActor::Build(ETrafficKind InKind)
{
	Kind = InKind;
	auto Sidelights = [&](float X, float Y, float Z)
	{
		Light(FVector(X, Y, Z), NavGreen, Starboard[0], Starboard[1]);
		Light(FVector(X, -Y, Z), NavRed, Port[0], Port[1]);
	};
	auto Stern = [&](float X, float Z, const FLinearColor& Color = NavWhite) { Light(FVector(X, 0.f, Z), Color, 112.5f, 247.5f); };
	switch (Kind)
	{
	case ETrafficKind::Powerboat:
	{
		// A 21 ft center console: white hull, blue boot stripe, console and outboard.
		Part(Cube, FVector(-0.3, 0, 0.35), FVector(4.6, 2.3, 0.8), White);
		Part(Cube, FVector(2.3, 0, 0.4), FVector(1.7, 1.6, 0.75), White, FRotator(0, 0, 0));
		Part(Cube, FVector(-0.3, 0, -0.02), FVector(4.6, 2.32, 0.12), FLinearColor(0.05f, 0.15f, 0.45f));
		Part(Cube, FVector(0.4, 0, 1.2), FVector(0.7, 0.8, 1.0), White);
		Part(Cylinder, FVector(-2.75, 0, 0.6), FVector(0.35, 0.35, 1.2), Dark);
		Part(Cylinder, FVector(-0.3, 0, 1.3), FVector(0.45, 0.45, 1.2), FLinearColor(0.9f, 0.6f, 0.1f));
		// Rule 23(c): under 12 m, sidelights and an all-round white light instead of masthead and stern lights.
		Sidelights(2.6f, 0.6f, 0.95f);
		Light(FVector(-2.6f, 0.f, 2.4f), NavWhite, AllRound[0], AllRound[1]);
		Part(Cylinder, FVector(-2.6, 0, 1.6), FVector(0.05, 0.05, 1.6), Steel);
		break;
	}
	case ETrafficKind::Trawler:
	case ETrafficKind::Committee:
	{
		const bool bCommittee = Kind == ETrafficKind::Committee;
		const float L = bCommittee ? 11.f : 21.f, B = bCommittee ? 3.8f : 6.5f;
		Part(Cube, FVector(0, 0, 0.6), FVector(L * 0.85f, B, 2.0), bCommittee ? White : FLinearColor(0.15f, 0.3f, 0.2f));
		Part(Cube, FVector(L * 0.42f, 0, 0.8), FVector(L * 0.2f, B * 0.7f, 1.8), bCommittee ? White : FLinearColor(0.15f, 0.3f, 0.2f), FRotator(0, 45, 0));
		Part(Cube, FVector(L * 0.18f, 0, 2.6), FVector(L * 0.22f, B * 0.6f, 2.2), White);
		const float MastX = bCommittee ? 0.f : L * 0.02f, MastH = bCommittee ? 6.f : 11.f;
		Part(Cylinder, FVector(MastX, 0, 1.6 + MastH * 0.5f), FVector(0.25, 0.25, MastH), Steel);
		if (bCommittee)
		{
			// The race committee's orange flag, and at anchor: a white all-round light (Rule 30) and a black ball by day.
			Part(Cube, FVector(MastX - 0.6f, 0, 1.6 + MastH - 0.5f), FVector(1.2, 0.03, 0.8), FLinearColor(1.f, 0.35f, 0.02f));
			Light(FVector(L * 0.4f, 0.f, 4.f), NavWhite, AllRound[0], AllRound[1]);
			DayShapes.Add(Part(Sphere, FVector(L * 0.4f, 0, 3.4), FVector(0.6), Dark));
			Part(Cylinder, FVector(L * 0.4f, 0, 2.6), FVector(0.06, 0.06, 1.6), Steel);
			break;
		}
		// Outriggers swung out with the nets towing astern.
		Part(Cylinder, FVector(MastX, 4.5, 4.5), FVector(0.15, 0.15, 10.0), Steel, FRotator(0, 0, -60));
		Part(Cylinder, FVector(MastX, -4.5, 4.5), FVector(0.15, 0.15, 10.0), Steel, FRotator(0, 0, 60));
		Part(Cylinder, FVector(-12.0, 9.0, 0.8), FVector(0.04, 0.04, 26.0), Dark, FRotator(80, 18, 0));
		Part(Cylinder, FVector(-12.0, -9.0, 0.8), FVector(0.04, 0.04, 26.0), Dark, FRotator(80, -18, 0));
		// Rule 26(b): trawling, green over white all-round; by day two cones with their points together.
		Light(FVector(MastX, 0.f, 1.6f + MastH + 0.6f), NavGreen, AllRound[0], AllRound[1]);
		Light(FVector(MastX, 0.f, 1.6f + MastH - 0.6f), NavWhite, AllRound[0], AllRound[1]);
		DayShapes.Add(Part(Cone, FVector(MastX + 0.4f, 0, 1.6 + MastH - 2.4f), FVector(0.8, 0.8, 0.8), Dark, FRotator(180, 0, 0)));
		DayShapes.Add(Part(Cone, FVector(MastX + 0.4f, 0, 1.6 + MastH - 3.2f), FVector(0.8, 0.8, 0.8), Dark));
		Sidelights(L * 0.2f, B * 0.32f, 3.4f);
		Stern(-L * 0.42f, 2.0f);
		break;
	}
	case ETrafficKind::TugAndTow:
	{
		// A towboat pushing two hopper barges ahead: 120 m in all. Barges forward of the tug.
		const FLinearColor Rust(0.35f, 0.15f, 0.07f), Hopper(0.18f, 0.18f, 0.2f);
		Part(Cube, FVector(31.0, 0, 1.0), FVector(58.0, 10.6, 3.6), Rust);
		Part(Cube, FVector(31.0, 0, 3.0), FVector(52.0, 8.0, 0.8), Hopper);
		Part(Cube, FVector(-15.0, 0, 1.0), FVector(32.0, 10.6, 3.6), Rust);
		Part(Cube, FVector(-15.0, 0, 3.0), FVector(28.0, 8.0, 0.8), Hopper);
		Part(Cube, FVector(-45.0, 0, 1.4), FVector(26.0, 10.0, 3.6), White);
		Part(Cube, FVector(-46.0, 0, 5.4), FVector(12.0, 8.0, 4.4), White);
		Part(Cube, FVector(-46.0, 0, 9.3), FVector(6.0, 7.0, 3.4), FLinearColor(0.15f, 0.25f, 0.45f));
		Part(Cylinder, FVector(-46.0, 0, 13.5), FVector(0.3, 0.3, 5.0), Steel);
		// Pushing ahead (Rule 24(c)): two masthead lights, sidelights, sternlight; sidelights also at the head of the tow.
		Light(FVector(-46.f, 0.f, 15.6f), NavWhite, Masthead[0], Masthead[1]);
		Light(FVector(-46.f, 0.f, 14.6f), NavWhite, Masthead[0], Masthead[1]);
		Sidelights(59.5f, 5.0f, 3.2f);
		Sidelights(-44.f, 3.6f, 9.0f);
		Stern(-58.f, 4.0f);
		// Restricted in her ability to maneuver (Rule 27(b)): red-white-red all-round; ball-diamond-ball by day.
		Light(FVector(-47.f, 0.f, 13.6f), NavRed, AllRound[0], AllRound[1]);
		Light(FVector(-47.f, 0.f, 12.8f), NavWhite, AllRound[0], AllRound[1]);
		Light(FVector(-47.f, 0.f, 12.0f), NavRed, AllRound[0], AllRound[1]);
		DayShapes.Add(Part(Sphere, FVector(-45.0, 0, 13.2), FVector(0.7), Dark));
		DayShapes.Add(Part(Cube, FVector(-45.0, 0, 12.3), FVector(0.5, 0.5, 0.5), Dark, FRotator(45, 0, 45)));
		DayShapes.Add(Part(Sphere, FVector(-45.0, 0, 11.4), FVector(0.7), Dark));
		break;
	}
	case ETrafficKind::Ship:
	{
		// A product tanker: black topsides, red boot top, white house aft, a funnel; pipework on deck.
		const float L = 230.f, B = 32.f;
		Part(Cube, FVector(-5, 0, 4.0), FVector(L * 0.86f, B, 14.0), FLinearColor(0.07f, 0.08f, 0.1f));
		Part(Cube, FVector(L * 0.45f, 0, 4.5), FVector(L * 0.16f, B * 0.72f, 13.0), FLinearColor(0.07f, 0.08f, 0.1f), FRotator(0, 45, 0));
		Part(Cube, FVector(-5, 0, -2.2), FVector(L * 0.86f, B + 0.1f, 1.8), FLinearColor(0.45f, 0.07f, 0.06f));
		Part(Cube, FVector(-90, 0, 18.0), FVector(18.0, B * 0.9f, 14.0), White);
		Part(Cube, FVector(-92, 0, 26.5), FVector(10.0, B * 1.02f, 3.0), White);
		Part(Cylinder, FVector(-100, 0, 28.0), FVector(5.0, 5.0, 12.0), FLinearColor(0.75f, 0.1f, 0.08f));
		Part(Cube, FVector(10, 0, 11.6), FVector(150.0, 2.0, 1.2), FLinearColor(0.4f, 0.4f, 0.1f));
		Part(Cylinder, FVector(60, 0, 21.0), FVector(0.6, 0.6, 20.0), Steel);
		Part(Cylinder, FVector(-90, 0, 36.0), FVector(0.4, 0.4, 12.0), Steel);
		// Masthead lights forward and higher aft (Rule 23(a)), sidelights on the bridge wings, sternlight.
		Light(FVector(60.f, 0.f, 31.f), NavWhite, Masthead[0], Masthead[1]);
		Light(FVector(-90.f, 0.f, 42.f), NavWhite, Masthead[0], Masthead[1]);
		Sidelights(-86.f, B * 0.5f + 0.4f, 27.f);
		Stern(-114.f, 12.f);
		// Constrained by her draft (Rule 28): three all-round reds in a vertical line; a cylinder by day.
		Light(FVector(-92.f, 0.f, 40.f), NavRed, AllRound[0], AllRound[1]);
		Light(FVector(-92.f, 0.f, 38.f), NavRed, AllRound[0], AllRound[1]);
		Light(FVector(-92.f, 0.f, 36.f), NavRed, AllRound[0], AllRound[1]);
		DayShapes.Add(Part(Cylinder, FVector(-88, 0, 38.5), FVector(1.5, 1.5, 3.0), Dark));
		break;
	}
	default:
		break;
	}
}

void APowerVesselActor::UpdateFrom(const FTrafficVessel& V, bool bDark, const FVector& Observer, float Time)
{
	const FVesselSnapshot S = V.Snapshot();
	// A little pitch and roll so she is not frozen on the water; heavier vessels move less.
	const float Motion = FMath::Clamp(6.f / float(V.Power.Type.Length), 0.02f, 0.6f);
	const FRotator Rot(Motion * FMath::Sin(Time * 0.9f + S.Id), FMath::RadiansToDegrees(S.Heading), Motion * 1.6f * FMath::Sin(Time * 0.7f + 2.f * S.Id));
	SetActorLocationAndRotation(FVector(S.X, S.Y, 0.0) * 100.0, Rot);
	const FVector D = Observer - GetActorLocation();
	const float Rel = FMath::UnwindDegrees(FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X) - S.Heading));
	const float Dist = float(D.Size()) / 100.f;
	for (const FNavLight& L : Lights)
	{
		bool bArc;
		if (L.ArcTo > 180.f) bArc = Rel >= L.ArcFrom || Rel <= L.ArcTo - 360.f; // a sternlight's arc wraps through 180
		else bArc = Rel >= L.ArcFrom && Rel <= L.ArcTo;
		const bool bOn = bDark && bArc;
		L.Mesh->SetVisibility(bOn);
		// Drawn at least about two pixels across at any distance, as a light is seen.
		if (bOn) L.Mesh->SetRelativeScale3D(FVector(FMath::Max(0.25f, Dist * 0.0025f)));
	}
	for (UStaticMeshComponent* Shape : DayShapes) Shape->SetVisibility(!bDark);
}
