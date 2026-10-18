#include "ScriptedScene.h"
#include "SailingMath.h"
#include <cmath>
#include <cstdlib>
#include <algorithm>

namespace Sailing
{
	// A small JSON reader (the scene file is ours and small; SailingPhysics has no Unreal Json and builds standalone).
	namespace SceneJson
	{
		struct FValue
		{
			enum class EType : unsigned char { Null, Bool, Number, String, Array, Object };
			EType Type = EType::Null;
			bool B = false;
			double N = 0.0;
			std::string S;
			std::vector<FValue> Items;     // array items, or object values
			std::vector<std::string> Keys; // object keys (Keys[i] names Items[i])

			const FValue* Get(const char* Key) const
			{
				if (Type != EType::Object) return nullptr;
				for (size_t I = 0; I < Keys.size(); ++I) if (Keys[I] == Key) return &Items[I];
				return nullptr;
			}
		};

		class FReader
		{
		public:
			explicit FReader(const std::string& InText) : Text(InText) {}
			bool Read(FValue& Out, std::string& OutError)
			{
				if (!Value(Out, 0)) { OutError = Error; return false; }
				Skip();
				if (Pos != Text.size()) { OutError = Where("text after the end"); return false; }
				return true;
			}

		private:
			const std::string& Text;
			size_t Pos = 0;
			std::string Error;

			std::string Where(const char* What) const
			{
				int LineNo = 1;
				for (size_t I = 0; I < Pos && I < Text.size(); ++I) LineNo += Text[I] == '\n';
				return std::string("JSON line ") + std::to_string(LineNo) + ": " + What;
			}
			bool Fail(const char* What) { if (Error.empty()) Error = Where(What); return false; }
			void Skip() { while (Pos < Text.size() && (Text[Pos] == ' ' || Text[Pos] == '\t' || Text[Pos] == '\n' || Text[Pos] == '\r')) ++Pos; }
			bool Literal(const char* Word)
			{
				const size_t L = std::char_traits<char>::length(Word);
				if (Text.compare(Pos, L, Word) != 0) return false;
				Pos += L;
				return true;
			}
			static void Utf8(unsigned Code, std::string& Out)
			{
				if (Code < 0x80) Out += char(Code);
				else if (Code < 0x800) { Out += char(0xC0 | (Code >> 6)); Out += char(0x80 | (Code & 0x3F)); }
				else if (Code < 0x10000) { Out += char(0xE0 | (Code >> 12)); Out += char(0x80 | ((Code >> 6) & 0x3F)); Out += char(0x80 | (Code & 0x3F)); }
				else { Out += char(0xF0 | (Code >> 18)); Out += char(0x80 | ((Code >> 12) & 0x3F)); Out += char(0x80 | ((Code >> 6) & 0x3F)); Out += char(0x80 | (Code & 0x3F)); }
			}
			bool Hex4(unsigned& Out)
			{
				if (Pos + 4 > Text.size()) return false;
				Out = 0;
				for (int I = 0; I < 4; ++I)
				{
					const char C = Text[Pos++];
					Out <<= 4;
					if (C >= '0' && C <= '9') Out |= unsigned(C - '0');
					else if (C >= 'a' && C <= 'f') Out |= unsigned(C - 'a' + 10);
					else if (C >= 'A' && C <= 'F') Out |= unsigned(C - 'A' + 10);
					else return false;
				}
				return true;
			}
			bool String(std::string& Out)
			{
				++Pos; // the opening quote
				while (Pos < Text.size())
				{
					const char C = Text[Pos++];
					if (C == '"') return true;
					if (static_cast<unsigned char>(C) < 0x20) return Fail("control character in a string");
					if (C != '\\') { Out += C; continue; }
					if (Pos >= Text.size()) break;
					const char E = Text[Pos++];
					switch (E)
					{
					case '"': Out += '"'; break;
					case '\\': Out += '\\'; break;
					case '/': Out += '/'; break;
					case 'b': Out += '\b'; break;
					case 'f': Out += '\f'; break;
					case 'n': Out += '\n'; break;
					case 'r': Out += '\r'; break;
					case 't': Out += '\t'; break;
					case 'u':
					{
						unsigned Code = 0;
						if (!Hex4(Code)) return Fail("bad \\u escape");
						if (Code >= 0xD800 && Code < 0xDC00 && Pos + 1 < Text.size() && Text[Pos] == '\\' && Text[Pos + 1] == 'u')
						{
							Pos += 2;
							unsigned Low = 0;
							if (!Hex4(Low) || Low < 0xDC00 || Low >= 0xE000) return Fail("bad surrogate pair");
							Code = 0x10000 + ((Code - 0xD800) << 10) + (Low - 0xDC00);
						}
						Utf8(Code, Out);
						break;
					}
					default: return Fail("bad escape in a string");
					}
				}
				return Fail("unterminated string");
			}
			bool Value(FValue& Out, int Depth)
			{
				if (Depth > 64) return Fail("nested too deeply");
				Skip();
				if (Pos >= Text.size()) return Fail("unexpected end");
				const char C = Text[Pos];
				if (C == '{')
				{
					Out.Type = FValue::EType::Object;
					++Pos;
					Skip();
					if (Pos < Text.size() && Text[Pos] == '}') { ++Pos; return true; }
					for (;;)
					{
						Skip();
						if (Pos >= Text.size() || Text[Pos] != '"') return Fail("expected a key");
						std::string Key;
						if (!String(Key)) return false;
						for (const std::string& K : Out.Keys) if (K == Key) return Fail("repeated key");
						Skip();
						if (Pos >= Text.size() || Text[Pos] != ':') return Fail("expected ':'");
						++Pos;
						Out.Keys.push_back(Key);
						Out.Items.emplace_back();
						if (!Value(Out.Items.back(), Depth + 1)) return false;
						Skip();
						if (Pos < Text.size() && Text[Pos] == ',') { ++Pos; continue; }
						if (Pos < Text.size() && Text[Pos] == '}') { ++Pos; return true; }
						return Fail("expected ',' or '}'");
					}
				}
				if (C == '[')
				{
					Out.Type = FValue::EType::Array;
					++Pos;
					Skip();
					if (Pos < Text.size() && Text[Pos] == ']') { ++Pos; return true; }
					for (;;)
					{
						Out.Items.emplace_back();
						if (!Value(Out.Items.back(), Depth + 1)) return false;
						Skip();
						if (Pos < Text.size() && Text[Pos] == ',') { ++Pos; continue; }
						if (Pos < Text.size() && Text[Pos] == ']') { ++Pos; return true; }
						return Fail("expected ',' or ']'");
					}
				}
				if (C == '"') { Out.Type = FValue::EType::String; return String(Out.S); }
				if (Literal("true")) { Out.Type = FValue::EType::Bool; Out.B = true; return true; }
				if (Literal("false")) { Out.Type = FValue::EType::Bool; Out.B = false; return true; }
				if (Literal("null")) { Out.Type = FValue::EType::Null; return true; }
				if (C == '-' || (C >= '0' && C <= '9'))
				{
					const char* Begin = Text.c_str() + Pos;
					char* End = nullptr;
					Out.N = std::strtod(Begin, &End);
					if (End == Begin) return Fail("bad number");
					Pos += size_t(End - Begin);
					Out.Type = FValue::EType::Number;
					return true;
				}
				return Fail("unexpected character");
			}
		};

		/** Field readers that remember the first problem. */
		struct FCheck
		{
			std::string Error;
			bool Ok() const { return Error.empty(); }
			void Bad(const std::string& Where, const std::string& What) { if (Error.empty()) Error = Where + ": " + What; }

			void OnlyKeys(const FValue& O, const std::string& Where, std::initializer_list<const char*> Allowed)
			{
				for (const std::string& K : O.Keys)
				{
					bool bKnown = false;
					for (const char* A : Allowed) bKnown |= K == A;
					if (!bKnown) Bad(Where, "unknown field \"" + K + "\"");
				}
			}
			double Num(const FValue& O, const char* Key, const std::string& Where, double Default, bool bRequired = false)
			{
				const FValue* V = O.Get(Key);
				if (!V) { if (bRequired) Bad(Where, std::string("missing ") + Key); return Default; }
				if (V->Type != FValue::EType::Number) { Bad(Where, std::string(Key) + " must be a number"); return Default; }
				return V->N;
			}
			std::string Str(const FValue& O, const char* Key, const std::string& Where, bool bRequired = false)
			{
				const FValue* V = O.Get(Key);
				if (!V) { if (bRequired) Bad(Where, std::string("missing ") + Key); return std::string(); }
				if (V->Type != FValue::EType::String) { Bad(Where, std::string(Key) + " must be a string"); return std::string(); }
				if (bRequired && V->S.empty()) Bad(Where, std::string(Key) + " is empty");
				return V->S;
			}
			bool Bool(const FValue& O, const char* Key, const std::string& Where)
			{
				const FValue* V = O.Get(Key);
				if (!V) return false;
				if (V->Type != FValue::EType::Bool) { Bad(Where, std::string(Key) + " must be true or false"); return false; }
				return V->B;
			}
			const FValue* Obj(const FValue& O, const char* Key, const std::string& Where, bool bRequired)
			{
				const FValue* V = O.Get(Key);
				if (!V) { if (bRequired) Bad(Where, std::string("missing ") + Key); return nullptr; }
				if (V->Type != FValue::EType::Object) { Bad(Where, std::string(Key) + " must be an object"); return nullptr; }
				return V;
			}
			std::vector<std::string> Names(const FValue& O, const char* Key, const std::string& Where)
			{
				std::vector<std::string> Out;
				const FValue* V = O.Get(Key);
				if (!V) return Out;
				if (V->Type != FValue::EType::Array) { Bad(Where, std::string(Key) + " must be a list"); return Out; }
				for (const FValue& I : V->Items)
				{
					if (I.Type != FValue::EType::String || I.S.empty()) { Bad(Where, std::string(Key) + " holds names only"); continue; }
					Out.push_back(I.S);
				}
				return Out;
			}
		};

		bool Contains(const std::vector<std::string>& List, const std::string& S) { return std::find(List.begin(), List.end(), S) != List.end(); }
	}

	const char* SceneTriggerName(ESceneTrigger T)
	{
		static const char* Names[] = { "previous", "time", "gust", "twa", "heel", "speed", "past-mark" };
		return int(T) < int(ESceneTrigger::Count) ? Names[int(T)] : "?";
	}

	const char* SceneExpectName(ESceneExpect E)
	{
		static const char* Names[] = { "none", "sheet", "tack", "gybe", "hold", "station", "action" };
		return int(E) < int(ESceneExpect::Count) ? Names[int(E)] : "?";
	}

	bool FScriptedScene::LoadText(const std::string& Json, std::string* OutError)
	{
		using namespace SceneJson;
		*this = FScriptedScene();
		FValue Root;
		std::string ParseError;
		if (!FReader(Json).Read(Root, ParseError) || Root.Type != FValue::EType::Object)
		{
			if (OutError) *OutError = ParseError.empty() ? std::string("the scene is not a JSON object") : ParseError;
			return false;
		}
		FCheck C;
		C.OnlyKeys(Root, "scene", { "schema_version", "id", "title", "setting", "assist_caption", "cameras", "stations", "actions", "steps" });
		if (C.Num(Root, "schema_version", "scene", 0.0, true) != 1.0) C.Bad("scene", "schema_version must be 1");
		FScriptedScene S;
		S.Id = C.Str(Root, "id", "scene", true);
		S.Title = C.Str(Root, "title", "scene", true);
		S.AssistCaption = C.Str(Root, "assist_caption", "scene");
		S.Cameras = C.Names(Root, "cameras", "scene");
		S.Stations = C.Names(Root, "stations", "scene");
		S.Actions = C.Names(Root, "actions", "scene");
		if (const FValue* Set = C.Obj(Root, "setting", "scene", true))
		{
			C.OnlyKeys(*Set, "setting", { "boat", "world", "weather", "rain", "wind_kn", "gust_kn", "sea_hs_m", "stand_in", "then" });
			S.Setting.Boat = C.Str(*Set, "boat", "setting", true);
			S.Setting.World = C.Str(*Set, "world", "setting");
			S.Setting.Weather = C.Str(*Set, "weather", "setting");
			S.Setting.Rain = C.Str(*Set, "rain", "setting");
			S.Setting.WindKn = C.Num(*Set, "wind_kn", "setting", 0.0, true);
			S.Setting.GustKn = C.Num(*Set, "gust_kn", "setting", S.Setting.WindKn);
			S.Setting.SeaHsM = C.Num(*Set, "sea_hs_m", "setting", 0.0);
			if (const FValue* In = C.Obj(*Set, "stand_in", "setting", false))
			{
				C.OnlyKeys(*In, "setting.stand_in", { "boat", "wind_kn", "gust_kn" });
				S.Setting.StandInBoat = C.Str(*In, "boat", "setting.stand_in", true);
				S.Setting.StandInWindKn = C.Num(*In, "wind_kn", "setting.stand_in", S.Setting.WindKn);
				S.Setting.StandInGustKn = C.Num(*In, "gust_kn", "setting.stand_in", S.Setting.StandInWindKn);
			}
			if (const FValue* Then = C.Obj(*Set, "then", "setting", false))
			{
				C.OnlyKeys(*Then, "setting.then", { "cut", "tier" });
				S.Setting.ThenCut = C.Str(*Then, "cut", "setting.then");
				S.Setting.ThenTier = C.Str(*Then, "tier", "setting.then");
			}
		}
		const FValue* StepList = Root.Get("steps");
		if (!StepList || StepList->Type != FValue::EType::Array || StepList->Items.empty()) C.Bad("scene", "steps must be a non-empty list");
		else
		{
			for (const FValue& V : StepList->Items)
			{
				const std::string Where = "step " + std::to_string(S.Steps.size() + 1);
				if (V.Type != FValue::EType::Object) { C.Bad(Where, "not an object"); continue; }
				C.OnlyKeys(V, Where, { "id", "trigger", "call", "expect", "retry_after_s", "crew_takes_over_after", "next", "checkpoint", "restart", "camera" });
				FSceneStep St;
				St.Id = C.Str(V, "id", Where, true);
				const std::string W = St.Id.empty() ? Where : St.Id;
				for (const FSceneStep& Other : S.Steps) if (Other.Id == St.Id && !St.Id.empty()) C.Bad(W, "repeated step id");
				if (St.Id == "end") C.Bad(W, "\"end\" is reserved for next");
				St.RetryAfterSeconds = C.Num(V, "retry_after_s", W, St.RetryAfterSeconds);
				St.CrewTakesOverAfter = int(C.Num(V, "crew_takes_over_after", W, St.CrewTakesOverAfter));
				if (St.RetryAfterSeconds < 0.0 || St.CrewTakesOverAfter < 0) C.Bad(W, "retry_after_s and crew_takes_over_after must not be negative");
				St.Next = C.Str(V, "next", W);
				St.bCheckpoint = C.Bool(V, "checkpoint", W);
				St.Camera = C.Str(V, "camera", W);
				if (!St.Camera.empty() && !Contains(S.Cameras, St.Camera)) C.Bad(W, "camera \"" + St.Camera + "\" is not in the scene's cameras");
				if (const FValue* R = C.Obj(V, "restart", W, false))
				{
					C.OnlyKeys(*R, W + ".restart", { "twa_deg", "speed_kn" });
					St.bRestartPose = true;
					St.RestartTwaDeg = C.Num(*R, "twa_deg", W + ".restart", 0.0, true);
					St.RestartSpeedKn = C.Num(*R, "speed_kn", W + ".restart", 0.0);
				}
				if (St.bRestartPose && !St.bCheckpoint) C.Bad(W, "a restart pose belongs on a checkpoint");

				if (const FValue* T = C.Obj(V, "trigger", W, true))
				{
					const std::string TW = W + ".trigger";
					const std::string Type = C.Str(*T, "type", TW, true);
					int Found = -1;
					for (int I = 0; I < int(ESceneTrigger::Count); ++I) if (Type == SceneTriggerName(ESceneTrigger(I))) Found = I;
					if (Found < 0 && !Type.empty()) C.Bad(TW, "unknown trigger \"" + Type + "\"");
					FSceneTrigger& Tr = St.Trigger;
					Tr.Type = Found < 0 ? ESceneTrigger::Previous : ESceneTrigger(Found);
					Tr.AfterSeconds = C.Num(*T, "after_s", TW, 0.0);
					Tr.OrAfterSeconds = C.Num(*T, "or_after_s", TW, -1.0);
					switch (Tr.Type)
					{
					case ESceneTrigger::Time: C.OnlyKeys(*T, TW, { "type", "at_s", "after_s" }); Tr.AtSeconds = C.Num(*T, "at_s", TW, 0.0, true); break;
					case ESceneTrigger::Gust: C.OnlyKeys(*T, TW, { "type", "over_mean_kn", "after_s", "or_after_s" }); Tr.OverMeanKn = C.Num(*T, "over_mean_kn", TW, 0.0, true); break;
					case ESceneTrigger::Twa:
						C.OnlyKeys(*T, TW, { "type", "twa_min_deg", "twa_max_deg", "after_s", "or_after_s" });
						Tr.TwaMinDeg = C.Num(*T, "twa_min_deg", TW, 0.0, true);
						Tr.TwaMaxDeg = C.Num(*T, "twa_max_deg", TW, 180.0, true);
						if (Tr.TwaMinDeg > Tr.TwaMaxDeg) C.Bad(TW, "twa_min_deg above twa_max_deg");
						break;
					case ESceneTrigger::Heel: C.OnlyKeys(*T, TW, { "type", "heel_above_deg", "after_s", "or_after_s" }); Tr.HeelAboveDeg = C.Num(*T, "heel_above_deg", TW, 0.0, true); break;
					case ESceneTrigger::Speed: C.OnlyKeys(*T, TW, { "type", "speed_above_kn", "after_s", "or_after_s" }); Tr.SpeedAboveKn = C.Num(*T, "speed_above_kn", TW, 0.0, true); break;
					case ESceneTrigger::PastMark:
						C.OnlyKeys(*T, TW, { "type", "bearing_deg", "meters", "after_s", "or_after_s" });
						Tr.BearingDeg = C.Num(*T, "bearing_deg", TW, 0.0, true);
						Tr.Meters = C.Num(*T, "meters", TW, 0.0, true);
						break;
					case ESceneTrigger::Previous:
					case ESceneTrigger::Count:
					default: C.OnlyKeys(*T, TW, { "type", "after_s", "or_after_s" }); break;
					}
				}
				if (const FValue* Cl = C.Obj(V, "call", W, true))
				{
					C.OnlyKeys(*Cl, W + ".call", { "id", "caption", "retry", "ok" });
					St.Call.Id = C.Str(*Cl, "id", W + ".call", true);
					St.Call.Caption = C.Str(*Cl, "caption", W + ".call", true);
					St.Call.Retry = C.Str(*Cl, "retry", W + ".call");
					St.Call.Ok = C.Str(*Cl, "ok", W + ".call");
				}
				if (const FValue* E = C.Obj(V, "expect", W, true))
				{
					const std::string EW = W + ".expect";
					const std::string Type = C.Str(*E, "type", EW, true);
					int Found = -1;
					for (int I = 0; I < int(ESceneExpect::Count); ++I) if (Type == SceneExpectName(ESceneExpect(I))) Found = I;
					if (Found < 0 && !Type.empty()) C.Bad(EW, "unknown expectation \"" + Type + "\"");
					FSceneExpectation& Ex = St.Expect;
					Ex.Type = Found < 0 ? ESceneExpect::None : ESceneExpect(Found);
					Ex.WithinSeconds = C.Num(*E, "within_s", EW, Ex.WithinSeconds);
					if (Ex.WithinSeconds <= 0.0) C.Bad(EW, "within_s must be positive");
					switch (Ex.Type)
					{
					case ESceneExpect::None: C.OnlyKeys(*E, EW, { "type", "seconds" }); Ex.Seconds = C.Num(*E, "seconds", EW, 0.0, true); break;
					case ESceneExpect::Sheet:
						C.OnlyKeys(*E, EW, { "type", "sheet", "by", "at_least", "at_most", "within_s" });
						Ex.Sheet = C.Str(*E, "sheet", EW, true);
						if (!Ex.Sheet.empty() && Ex.Sheet != "main" && Ex.Sheet != "jib") C.Bad(EW, "sheet must be main or jib");
						Ex.By = C.Num(*E, "by", EW, 0.0);
						Ex.AtLeast = C.Num(*E, "at_least", EW, -1.0);
						Ex.AtMost = C.Num(*E, "at_most", EW, -1.0);
						if (Ex.By == 0.0 && Ex.AtLeast < 0.0 && Ex.AtMost < 0.0) C.Bad(EW, "a sheet expectation needs by, at_least or at_most");
						break;
					case ESceneExpect::Tack:
					case ESceneExpect::Gybe: C.OnlyKeys(*E, EW, { "type", "within_s" }); break;
					case ESceneExpect::Hold:
						C.OnlyKeys(*E, EW, { "type", "hold_s", "twa_min_deg", "twa_max_deg", "max_heel_deg", "min_speed_kn", "station", "within_s" });
						Ex.HoldSeconds = C.Num(*E, "hold_s", EW, 0.0, true);
						Ex.TwaMinDeg = C.Num(*E, "twa_min_deg", EW, -1.0);
						Ex.TwaMaxDeg = C.Num(*E, "twa_max_deg", EW, -1.0);
						Ex.MaxHeelDeg = C.Num(*E, "max_heel_deg", EW, -1.0);
						Ex.MinSpeedKn = C.Num(*E, "min_speed_kn", EW, -1.0);
						Ex.Station = C.Str(*E, "station", EW);
						if ((Ex.TwaMinDeg < 0.0) != (Ex.TwaMaxDeg < 0.0)) C.Bad(EW, "a TWA band needs both twa_min_deg and twa_max_deg");
						break;
					case ESceneExpect::Station: C.OnlyKeys(*E, EW, { "type", "station", "within_s" }); Ex.Station = C.Str(*E, "station", EW, true); break;
					case ESceneExpect::Action: C.OnlyKeys(*E, EW, { "type", "action", "within_s" }); Ex.Action = C.Str(*E, "action", EW, true); break;
					case ESceneExpect::Count:
					default: break;
					}
					if (!Ex.Station.empty() && !Contains(S.Stations, Ex.Station)) C.Bad(EW, "station \"" + Ex.Station + "\" is not in the scene's stations");
					if (!Ex.Action.empty() && !Contains(S.Actions, Ex.Action)) C.Bad(EW, "action \"" + Ex.Action + "\" is not in the scene's actions");
				}
				S.Steps.push_back(St);
			}
			for (const FSceneStep& St : S.Steps)
			{
				if (St.Next.empty() || St.Next == "end") continue;
				bool bFound = false;
				for (const FSceneStep& Other : S.Steps) bFound |= Other.Id == St.Next;
				if (!bFound) C.Bad(St.Id, "next names no step: \"" + St.Next + "\"");
			}
		}
		if (!C.Ok())
		{
			if (OutError) *OutError = C.Error;
			return false;
		}
		*this = S;
		return true;
	}

	void FScriptedScene::Start(const FBoatModel& Boat, double InMeanWindKn)
	{
		if (Steps.empty()) return;
		MeanWindKn = InMeanWindKn;
		Elapsed = 0.0;
		const Vec3 O = Boat.OriginPosition();
		StartX = O.X;
		StartY = O.Y;
		Result = FSceneResult();
		Result.SceneId = Id;
		CheckpointId.clear();
		CheckpointIndex = 0;
		OkUntil = -1.0;
		Enter(0);
	}

	void FScriptedScene::Enter(int Index)
	{
		Current = Index;
		Phase = EPhase::Waiting;
		EnteredAt = Elapsed;
		Repeats = 0;
		RepeatAt = -1.0;
		HeldFor = 0.0;
		ActionsDone.clear();
		const FSceneStep& S = Steps[size_t(Index)];
		if (S.bCheckpoint) { CheckpointId = S.Id; CheckpointIndex = Index; }
	}

	void FScriptedScene::RestartFromCheckpoint()
	{
		if (Steps.empty() || Phase == EPhase::Idle) return;
		++Result.Restarts;
		Result.bComplete = false;
		OkUntil = -1.0;
		Enter(CheckpointIndex);
	}

	bool FScriptedScene::Triggered(const FSceneStep& S, const FBoatModel& Boat) const
	{
		const FSceneTrigger& T = S.Trigger;
		const double Wait = Elapsed - EnteredAt;
		if (Wait < T.AfterSeconds) return false;
		if (T.Type == ESceneTrigger::Time) return Elapsed >= T.AtSeconds;
		if (T.OrAfterSeconds >= 0.0 && Wait >= T.OrAfterSeconds) return true;
		const FBoatTelemetry& Tel = Boat.GetTelemetry();
		switch (T.Type)
		{
		case ESceneTrigger::Gust: return Tel.TrueWindSpeed / kKnot >= MeanWindKn + T.OverMeanKn;
		case ESceneTrigger::Twa:
		{
			const double Twa = std::fabs(Tel.TrueWindAngle) / kDegToRad;
			return Twa >= T.TwaMinDeg && Twa <= T.TwaMaxDeg;
		}
		case ESceneTrigger::Heel: return std::fabs(Tel.Heel) / kDegToRad > T.HeelAboveDeg;
		case ESceneTrigger::Speed: return Tel.BoatSpeed / kKnot > T.SpeedAboveKn;
		case ESceneTrigger::PastMark:
		{
			const Vec3 O = Boat.OriginPosition();
			const double B = T.BearingDeg * kDegToRad; // map frame: +X north, +Y east
			return (O.X - StartX) * std::cos(B) + (O.Y - StartY) * std::sin(B) >= T.Meters;
		}
		case ESceneTrigger::Previous: return true;
		case ESceneTrigger::Time:
		case ESceneTrigger::Count:
		default: return false;
		}
	}

	void FScriptedScene::MakeCall(const FBoatModel& Boat, const FSceneInput& In)
	{
		const FSceneStep& S = Steps[size_t(Current)];
		Phase = EPhase::Calling;
		CallAt = FirstCallAt = Elapsed;
		WindowEnd = Elapsed + S.Expect.WithinSeconds;
		RepeatAt = -1.0;
		++CallSerial;
		SheetAtCall = S.Expect.Sheet == "main" ? In.Controls.MainSheet : In.Controls.JibSheet;
		SideAtCall = Boat.GetTelemetry().TrueWindAngle >= 0.0 ? 1 : -1;
		HeldFor = 0.0;
		ActionsDone.clear();
	}

	bool FScriptedScene::Answered(const FSceneStep& S, const FBoatModel& Boat, const FSceneInput& In, double Dt)
	{
		const FSceneExpectation& E = S.Expect;
		const FBoatTelemetry& Tel = Boat.GetTelemetry();
		switch (E.Type)
		{
		case ESceneExpect::None: return Elapsed - FirstCallAt >= E.Seconds;
		case ESceneExpect::Sheet:
		{
			const double V = E.Sheet == "main" ? In.Controls.MainSheet : In.Controls.JibSheet;
			bool bOk = true;
			// "By" counts from where the sheet was at the first call, short of the stops (a sheet already near fully
			// eased can only go as far as it goes).
			if (E.By > 0.0) bOk &= V >= std::min(SheetAtCall + E.By, 0.98);
			if (E.By < 0.0) bOk &= V <= std::max(SheetAtCall + E.By, 0.02);
			if (E.AtLeast >= 0.0) bOk &= V >= E.AtLeast;
			if (E.AtMost >= 0.0) bOk &= V <= E.AtMost;
			return bOk;
		}
		case ESceneExpect::Tack:
		case ESceneExpect::Gybe:
		{
			const int Side = Tel.TrueWindAngle >= 0.0 ? 1 : -1;
			if (Side == SideAtCall) return false;
			const double Twa = std::fabs(Tel.TrueWindAngle) / kDegToRad;
			// Settled on the new side: a bow hung head to wind flickers across zero without having tacked.
			return E.Type == ESceneExpect::Tack ? Twa >= 30.0 && Twa < 100.0 : Twa > 100.0;
		}
		case ESceneExpect::Hold:
		{
			bool bOk = true;
			const double Twa = std::fabs(Tel.TrueWindAngle) / kDegToRad;
			if (E.TwaMinDeg >= 0.0) bOk &= Twa >= E.TwaMinDeg && Twa <= E.TwaMaxDeg;
			if (E.MaxHeelDeg >= 0.0) bOk &= std::fabs(Tel.Heel) / kDegToRad <= E.MaxHeelDeg;
			if (E.MinSpeedKn >= 0.0) bOk &= Tel.BoatSpeed / kKnot >= E.MinSpeedKn;
			if (!E.Station.empty()) bOk &= In.Station == E.Station;
			HeldFor = bOk ? HeldFor + Dt : 0.0;
			return HeldFor >= E.HoldSeconds;
		}
		case ESceneExpect::Station: return In.Station == E.Station;
		case ESceneExpect::Action: return SceneJson::Contains(ActionsDone, E.Action);
		case ESceneExpect::Count:
		default: return false;
		}
	}

	void FScriptedScene::Succeed(bool bAssisted)
	{
		const FSceneStep& S = Steps[size_t(Current)];
		(bAssisted ? Result.StepsAssisted : Result.StepsPassed)++;
		OkCaption = bAssisted ? AssistCaption : S.Call.Ok;
		OkUntil = OkCaption.empty() ? -1.0 : Elapsed + 3.0;
		int NextIndex = Current + 1;
		if (S.Next == "end") NextIndex = int(Steps.size());
		else if (!S.Next.empty())
		{
			for (size_t I = 0; I < Steps.size(); ++I) if (Steps[I].Id == S.Next) NextIndex = int(I);
		}
		if (NextIndex >= int(Steps.size()))
		{
			Phase = EPhase::Done;
			Result.bComplete = true;
			Result.Seconds = Elapsed;
			return;
		}
		Enter(NextIndex);
	}

	void FScriptedScene::Update(const FBoatModel& Boat, const FSceneInput& In, double Dt)
	{
		if (Phase == EPhase::Done) { Elapsed += Dt; return; } // the last "ok" still times out
		if (!IsActive()) return;
		Elapsed += Dt;
		Result.Seconds = Elapsed;
		const FSceneStep& S = Steps[size_t(Current)];
		if (Phase == EPhase::Waiting)
		{
			if (Triggered(S, Boat)) MakeCall(Boat, In);
			return;
		}
		for (const std::string& A : In.Actions) if (!SceneJson::Contains(ActionsDone, A)) ActionsDone.push_back(A);
		if (Answered(S, Boat, In, Dt)) { Succeed(false); return; }
		if (RepeatAt < 0.0 && Elapsed >= WindowEnd)
		{
			if (S.CrewTakesOverAfter > 0 && Repeats >= S.CrewTakesOverAfter) { Succeed(true); return; }
			RepeatAt = Elapsed + S.RetryAfterSeconds;
		}
		if (RepeatAt >= 0.0 && Elapsed >= RepeatAt)
		{
			++Repeats;
			++Result.Retries;
			++CallSerial;
			CallAt = Elapsed;
			WindowEnd = Elapsed + S.Expect.WithinSeconds;
			RepeatAt = -1.0;
		}
	}

	const std::string& FScriptedScene::GetCaption() const
	{
		static const std::string Empty;
		if (Phase == EPhase::Calling)
		{
			const FSceneStep& S = Steps[size_t(Current)];
			return Repeats > 0 && !S.Call.Retry.empty() ? S.Call.Retry : S.Call.Caption;
		}
		return Elapsed < OkUntil ? OkCaption : Empty;
	}

	const std::string& FScriptedScene::GetCallId() const
	{
		static const std::string Empty;
		const FSceneStep* S = GetStep();
		return Phase == EPhase::Calling && S ? S->Call.Id : Empty;
	}

	const std::string& FScriptedScene::GetCamera() const
	{
		static const std::string Empty;
		const FSceneStep* S = GetStep();
		return IsActive() && S ? S->Camera : Empty;
	}
}
