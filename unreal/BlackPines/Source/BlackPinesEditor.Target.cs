using UnrealBuildTool;
public class BlackPinesEditorTarget : TargetRules { public BlackPinesEditorTarget(TargetInfo Target) : base(Target) { Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.V5; ExtraModuleNames.Add("BlackPines"); } }
