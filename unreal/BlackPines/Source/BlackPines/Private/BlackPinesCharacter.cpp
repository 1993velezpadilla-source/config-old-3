#include "BlackPinesCharacter.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
ABlackPinesCharacter::ABlackPinesCharacter()
{
    GetCapsuleComponent()->InitCapsuleSize(34.f,88.f);
    GetCharacterMovement()->MaxWalkSpeed=450.f;
    GetCharacterMovement()->JumpZVelocity=425.f;
    GetCharacterMovement()->AirControl=0.3f;
    bUseControllerRotationYaw=true;
    GetCharacterMovement()->bOrientRotationToMovement=false;
    FPSCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FPSCamera->SetupAttachment(GetCapsuleComponent());
    FPSCamera->SetRelativeLocation(FVector(0.f,0.f,66.f));
    FPSCamera->bUsePawnControlRotation=true;
    FPSCamera->FieldOfView=85.f;
}
void ABlackPinesCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    check(Input);
    Input->BindAxis(TEXT("MoveForward"),this,&ABlackPinesCharacter::MoveForward);
    Input->BindAxis(TEXT("MoveRight"),this,&ABlackPinesCharacter::MoveRight);
    Input->BindAxis(TEXT("Turn"),this,&APawn::AddControllerYawInput);
    Input->BindAxis(TEXT("LookUp"),this,&APawn::AddControllerPitchInput);
    Input->BindAction(TEXT("Jump"),IE_Pressed,this,&ACharacter::Jump);
    Input->BindAction(TEXT("Jump"),IE_Released,this,&ACharacter::StopJumping);
}
void ABlackPinesCharacter::MoveForward(float V)
{
    if(Controller && !FMath::IsNearlyZero(V))
    {
        const FRotator YawOnly(0.f,Controller->GetControlRotation().Yaw,0.f);
        AddMovementInput(FRotationMatrix(YawOnly).GetUnitAxis(EAxis::X),V);
    }
}
void ABlackPinesCharacter::MoveRight(float V)
{
    if(Controller && !FMath::IsNearlyZero(V))
    {
        const FRotator YawOnly(0.f,Controller->GetControlRotation().Yaw,0.f);
        AddMovementInput(FRotationMatrix(YawOnly).GetUnitAxis(EAxis::Y),V);
    }
}
