#pragma once

#include <cmath>
#include <algorithm>

// Small vector math for the physics. Axes match Unreal: X forward, Y starboard, Z up, in meters.
// Rotations use the same quaternion algebra as FQuat, so a Quat can be copied straight into an FQuat.
// A positive rotation about +Z turns the bow from +X toward +Y (to starboard); about +X it lifts the
// starboard side (heel to port).
namespace Sailing
{
	constexpr double kPi = 3.14159265358979323846;
	constexpr double kDegToRad = kPi / 180.0;
	constexpr double kRadToDeg = 180.0 / kPi;
	constexpr double kGravity = 9.80665;          // m/s^2
	constexpr double kWaterDensity = 1000.0;      // kg/m^3, fresh water (Lake Ray Roberts)
	constexpr double kWaterViscosity = 1.05e-6;   // m^2/s, about 18 C
	constexpr double kAirDensity = 1.20;          // kg/m^3
	constexpr double kKnot = 0.514444;            // m/s per knot
	constexpr double kFoot = 0.3048;              // m per foot

	inline double Clamp(double V, double Lo, double Hi) { return V < Lo ? Lo : (V > Hi ? Hi : V); }
	inline double Lerp(double A, double B, double T) { return A + (B - A) * T; }
	inline double Sign(double V) { return V < 0.0 ? -1.0 : 1.0; }
	inline double SmoothStep(double Edge0, double Edge1, double X)
	{
		const double T = Clamp((X - Edge0) / (Edge1 - Edge0), 0.0, 1.0);
		return T * T * (3.0 - 2.0 * T);
	}
	/** Wraps an angle to (-pi, pi]. */
	inline double WrapAngle(double A)
	{
		A = std::fmod(A + kPi, 2.0 * kPi);
		if (A < 0.0) A += 2.0 * kPi;
		return A - kPi;
	}
	/** Moves Current toward Target by at most MaxDelta. */
	inline double MoveToward(double Current, double Target, double MaxDelta)
	{
		return Current + Clamp(Target - Current, -MaxDelta, MaxDelta);
	}

	struct Vec3
	{
		double X = 0.0, Y = 0.0, Z = 0.0;

		constexpr Vec3() = default;
		constexpr Vec3(double InX, double InY, double InZ) : X(InX), Y(InY), Z(InZ) {}

		Vec3 operator+(const Vec3& B) const { return { X + B.X, Y + B.Y, Z + B.Z }; }
		Vec3 operator-(const Vec3& B) const { return { X - B.X, Y - B.Y, Z - B.Z }; }
		Vec3 operator-() const { return { -X, -Y, -Z }; }
		Vec3 operator*(double S) const { return { X * S, Y * S, Z * S }; }
		Vec3 operator/(double S) const { return { X / S, Y / S, Z / S }; }
		Vec3& operator+=(const Vec3& B) { X += B.X; Y += B.Y; Z += B.Z; return *this; }
		Vec3& operator-=(const Vec3& B) { X -= B.X; Y -= B.Y; Z -= B.Z; return *this; }
		Vec3& operator*=(double S) { X *= S; Y *= S; Z *= S; return *this; }

		double Dot(const Vec3& B) const { return X * B.X + Y * B.Y + Z * B.Z; }
		Vec3 Cross(const Vec3& B) const { return { Y * B.Z - Z * B.Y, Z * B.X - X * B.Z, X * B.Y - Y * B.X }; }
		double Length() const { return std::sqrt(X * X + Y * Y + Z * Z); }
		double LengthXY() const { return std::sqrt(X * X + Y * Y); }
		Vec3 Normalized() const { const double L = Length(); return L > 1e-12 ? *this / L : Vec3(); }
		Vec3 Mul(const Vec3& B) const { return { X * B.X, Y * B.Y, Z * B.Z }; }
		Vec3 Div(const Vec3& B) const { return { X / B.X, Y / B.Y, Z / B.Z }; }
	};

	inline Vec3 operator*(double S, const Vec3& V) { return V * S; }

	struct Quat
	{
		double X = 0.0, Y = 0.0, Z = 0.0, W = 1.0;

		constexpr Quat() = default;
		constexpr Quat(double InX, double InY, double InZ, double InW) : X(InX), Y(InY), Z(InZ), W(InW) {}

		static Quat FromAxisAngle(const Vec3& Axis, double Angle)
		{
			const Vec3 N = Axis.Normalized();
			const double S = std::sin(Angle * 0.5);
			return { N.X * S, N.Y * S, N.Z * S, std::cos(Angle * 0.5) };
		}
		/** Heading (yaw about Z), then pitch (about Y), then heel (about X), all in radians. */
		static Quat FromYawPitchRoll(double Yaw, double Pitch, double Roll)
		{
			return FromAxisAngle({ 0, 0, 1 }, Yaw) * FromAxisAngle({ 0, 1, 0 }, Pitch) * FromAxisAngle({ 1, 0, 0 }, Roll);
		}

		Quat operator*(const Quat& B) const
		{
			return {
				W * B.X + X * B.W + Y * B.Z - Z * B.Y,
				W * B.Y - X * B.Z + Y * B.W + Z * B.X,
				W * B.Z + X * B.Y - Y * B.X + Z * B.W,
				W * B.W - X * B.X - Y * B.Y - Z * B.Z };
		}
		Quat Conjugate() const { return { -X, -Y, -Z, W }; }
		Quat Normalized() const
		{
			const double L = std::sqrt(X * X + Y * Y + Z * Z + W * W);
			return { X / L, Y / L, Z / L, W / L };
		}
		/** Body to world. Same formula as FQuat::RotateVector. */
		Vec3 Rotate(const Vec3& V) const
		{
			const Vec3 Q(X, Y, Z);
			const Vec3 T = Q.Cross(V) * 2.0;
			return V + T * W + Q.Cross(T);
		}
		/** World to body. */
		Vec3 Unrotate(const Vec3& V) const { return Conjugate().Rotate(V); }

		Vec3 Forward() const { return Rotate({ 1, 0, 0 }); }
		Vec3 Right() const { return Rotate({ 0, 1, 0 }); }
		Vec3 Up() const { return Rotate({ 0, 0, 1 }); }

		/** Compass-style heading of the bow in the XY plane, radians (0 = +X, positive toward +Y). */
		double Heading() const { const Vec3 F = Forward(); return std::atan2(F.Y, F.X); }
		/** Heel angle: positive when the starboard side is lifted (heeled to port). */
		double Heel() const { const Vec3 R = Right(); return std::asin(Clamp(R.Z, -1.0, 1.0)); }
		/** Tilt from upright, 0..pi: like the heel, but upside down reads pi (the heel reads ~0 there). */
		double Tilt() const { return std::acos(Clamp(Rotate(Vec3(0.0, 0.0, 1.0)).Z, -1.0, 1.0)); }
		/** Pitch: positive bow down (same sign as rotation about +Y). */
		double Pitch() const { const Vec3 F = Forward(); return -std::asin(Clamp(F.Z, -1.0, 1.0)); }
	};
}
