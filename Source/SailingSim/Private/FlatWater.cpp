#include "FlatWater.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AFlatWater::AFlatWater()
{
	PrimaryActorTick.bCanEverTick = false;

	Surface = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Surface"));
	RootComponent = Surface;
	Surface->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Surface->SetCastShadow(false);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (PlaneMesh.Succeeded())
	{
		Surface->SetStaticMesh(PlaneMesh.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BaseMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (BaseMaterial.Succeeded())
	{
		Surface->SetMaterial(0, BaseMaterial.Object);
	}
}

void AFlatWater::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	// The engine plane is 1 m square.
	Surface->SetRelativeScale3D(FVector(SizeMeters, SizeMeters, 1.0));

	if (UMaterialInstanceDynamic* Mid = Surface->CreateAndSetMaterialInstanceDynamic(0))
	{
		Mid->SetVectorParameterValue(TEXT("Color"), WaterColor);
	}
}
