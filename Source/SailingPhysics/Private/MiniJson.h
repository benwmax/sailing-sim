#pragma once

#include <cstdlib>
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * A small JSON reader for SailingPhysics' own data files (the prologue scene, the wildlife tables): SailingPhysics has
	 * no Unreal Json and builds standalone. Objects keep their key order; repeated keys are an error.
	 */
	namespace MiniJson
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

		inline double Number(const FValue* V, double Default) { return V && V->Type == FValue::EType::Number ? V->N : Default; }
		inline std::string String(const FValue* V) { return V && V->Type == FValue::EType::String ? V->S : std::string(); }
		inline bool Bool(const FValue* V, bool Default) { return V && V->Type == FValue::EType::Bool ? V->B : Default; }
	}
}
