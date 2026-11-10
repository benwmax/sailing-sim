#pragma once

/** #598: the seconds since she was put at her start, on the boat clock, not counting time the UI held her (the loading
 *  screen and the briefing run the clock while the boat waits). ASailboatPawn::GetSecondsSinceStart reads it. */
struct FSailStartClock
{
	void Reset(double Now) { Start = Now; if (HeldAt >= 0.0) HeldAt = Now; }
	void Hold(bool bHeld, double Now)
	{
		if (bHeld && HeldAt < 0.0) HeldAt = Now;
		else if (!bHeld && HeldAt >= 0.0) { Start += Now - HeldAt; HeldAt = -1.0; }
	}
	double Seconds(double Now) const { return (HeldAt >= 0.0 ? HeldAt : Now) - Start; }
private:
	double Start = 0.0;
	double HeldAt = -1.0;
};
