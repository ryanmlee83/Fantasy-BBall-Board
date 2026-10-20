"""Turn scout_league.py output into the data files behind the Zalgiris Scouting Report dashboard.

Usage: python scripts/build_scout_data.py   (reads reports/scout_260146*.json, writes reports/scout_260146_dash/)

Three runs feed it, one per assumption about missed weeks: none filled (backfill 0),
half filled (0.5, the central case) and all filled (1.0). The scouting notes below are
written from the half-filled run.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = {"none": "reports/scout_260146_backfill0.0.json", "half": "reports/scout_260146.json",
        "all": "reports/scout_260146_backfill1.0.json"}
OUT = ROOT / "reports" / "scout_260146_dash"
CAT_KEYS = {"FG%": "FG", "FT%": "FT", "3PM": "3PTM", "PTS": "PTS", "REB": "REB", "AST": "AST",
            "STL": "ST", "BLK": "BLK", "TO": "TO"}
ME = "Chop'em Down"
SHORT = {"Dominykas's Expert Team": "Dominykas", "Z - 12T": "Z - 12T", ME: "Chop'em Down",
         "Μαριος's Nice Team": "Μαριος", "MVP": "MVP", "…": "… (Edwards)",
         "Benius's Marvelous Team": "Benius", "Du po 50": "Du po 50", "Θανος's Neat Team": "Θανος",
         "Gökhan's Groovy Team": "Gökhan", "OJ7": "OJ7", "BC Blemba Normaliai's Team": "BC Blemba"}

# Scouting notes, written from the half-filled run (ranks out of 12 in brackets where useful).
NOTES = {
    "Z - 12T": dict(
        identity="Wembanyama-anchored bigs and long wings. Owns blocks and rebounds, shoots efficiently and protects the ball, but light on points and assists.",
        key_players="Victor Wembanyama, Trey Murphy III, Austin Reaves, Franz Wagner, Isaiah Hartenstein, Day'Ron Sharpe",
        risks="Few. Franz Wagner and Wembanyama are projected under 60 games, but the roster is deep in bigs who cover for each other. The steadiest team at every injury setting.",
        vs_me="Your toughest matchup. They take FG%, FT%, BLK and TO; you take 3PTM, PTS and AST; REB and ST lean their way. To steal the week you need to win the boards or steals."),
    "Μαριος's Nice Team": dict(
        identity="Shai Gilgeous-Alexander plus a deep frontcourt (Adebayo, Okongwu, Naz Reid, Derik Queen). Good at nearly everything except threes.",
        key_players="Shai Gilgeous-Alexander, Onyeka Okongwu, Bam Adebayo, Desmond Bane, Trae Young, VJ Edgecombe",
        risks="The healthiest roster in the league, so its edge is games played. Trae Young is projected for under 50 games. AJ Dybantsa is a rookie stand-in.",
        vs_me="Tough, but it depends on you. They win FG%, FT%, ST and TO; you win 3PTM. Much of their edge is health: if you fill your injured players' weeks from waivers, this becomes close to even."),
    "OJ7": dict(
        identity="Guard-heavy shooting build that gives up the boards. Best in the league at FT%, 3PTM and AST, last in REB, near the bottom in BLK and FG%.",
        key_players="Tyrese Haliburton, Donovan Mitchell, James Harden, Mikal Bridges, Pascal Siakam, Dejounte Murray",
        risks="Haliburton is back from a torn Achilles. Kevin Porter Jr. was waived by the Bucks, so that spot is a waiver pickup. Dejounte Murray and Ty Jerome are projected for about 40 games.",
        vs_me="The same kind of team as yours, built better. They win FT%, 3PTM, AST, ST and TO; you win REB and BLK by a lot and FG% narrowly. The most predictable tough matchup: it barely moves with the injury setting."),
    "BC Blemba Normaliai's Team": dict(
        identity="Defense-first wings and bigs. Top three in ST, BLK and TO, but near the bottom in points.",
        key_players="Kawhi Leonard, Scottie Barnes, Jalen Johnson, Derrick White, OG Anunoby, Kel'el Ware",
        risks="Kawhi Leonard is projected for about 50 games, Nic Claxton has a hamstring injury and Zach Edey is projected for about 40. Two rookies (Darius Acuff Jr., Mikel Brown Jr.) are stand-ins.",
        vs_me="Leans their way. They win FG%, ST, BLK and TO; you win 3PTM, PTS and AST. REB and FT% are coin flips, so those two decide it."),
    "…": dict(
        identity="Volume scoring with real size. Most points in the league and top three in rebounds (Duren, Gobert, Turner), but weak at FT%, ST and TO.",
        key_players="Anthony Edwards, Stephen Curry, Jalen Duren, Jalen Williams, Paolo Banchero, Rudy Gobert",
        risks="Stephen Curry (under 50 games), Ja Morant (about 40) and Jalen Williams (recurring hamstring) are all health questions. The team name is an ellipsis on Yahoo; Edwards was its first pick.",
        vs_me="Even. You edge AST, they edge FG%, and the other seven categories are close to coin flips."),
    "Dominykas's Expert Team": dict(
        identity="Nikola Jokić-centered passing and efficiency. Top three in FG% and AST, weak at 3PTM, ST and BLK.",
        key_players="Nikola Jokić, Devin Booker, Domantas Sabonis, LeBron James, Kyrie Irving, Paul George",
        risks="Plays the fewest games in the league: Jimmy Butler is out until at least January, and Kyrie Irving and Paul George are projected for about 43 games. After you, the team that gains most from filling missed weeks.",
        vs_me="Dead even. They win FG%, AST and TO; you win 3PTM and BLK."),
    ME: dict(
        identity="High-usage guards (Dončić, Ball, Giddey, Keyonte George, Coby White) with injury-prone bigs (Embiid, Robinson, Poeltl). Strong in 3PTM, AST and PTS, solid in REB and BLK, last in TO and 10th in FG%.",
        key_players="Luka Dončić, Jaren Jackson Jr., LaMelo Ball, Joel Embiid, Josh Giddey, Mitchell Robinson",
        risks="Third-fewest games of your own players in the league: Embiid, Robinson, Poeltl and LaMelo all miss a lot of time. Brandon Ingram is on IL until at least Nov 1.",
        vs_me=""),
    "MVP": dict(
        identity="Playmakers and pests (Cunningham, Daniels, Castle, Fox) with Holmgren, Davis and Şengün inside. Top three in AST and ST; weak at FT% and TO.",
        key_players="Chet Holmgren, Dyson Daniels, Cade Cunningham, Anthony Davis, Alperen Şengün, De'Aaron Fox",
        risks="Anthony Davis is projected for about 43 games. A deep wing bench (Podziemski, Grimes, Mathurin, Wiggins) covers injuries well.",
        vs_me="Slight edge to you. You win FT% and 3PTM; they win ST; the rest are close."),
    "Benius's Marvelous Team": dict(
        identity="Scoring guards (Murray, Brunson, Garland, LaVine) with efficient bigs and Giannis. Top two in FG% and PTS; giving up ST and BLK.",
        key_players="Jamal Murray, Jarrett Allen, Jalen Brunson, Michael Porter Jr., Giannis Antetokounmpo",
        risks="Zach LaVine and Aaron Gordon are projected for under 50 games.",
        vs_me="One of your better matchups. You win BLK easily and lean REB; they win FG% and TO."),
    "Θανος's Neat Team": dict(
        identity="Ball-secure guards (Maxey, Lillard, Pritchard, VanVleet) with Durant, Mobley and Zubac. Good at FT% and TO, weak on the boards and in steals.",
        key_players="Tyrese Maxey, Evan Mobley, Damian Lillard, Kevin Durant, Deni Avdija, Ivica Zubac",
        risks="Damian Lillard is back from a torn Achilles at 36. Fred VanVleet is returning from an ACL tear with an early minutes limit.",
        vs_me="One of your better matchups. You win REB and BLK; they win FT% and TO."),
    "Du po 50": dict(
        identity="Perimeter scorers and pests. Top three in 3PTM, PTS and ST, but last in FG% and weak in REB, AST and BLK.",
        key_players="Jayson Tatum, Amen Thompson, Lauri Markkanen, Jaylen Brown, Nickeil Alexander-Walker, Cason Wallace",
        risks="Tatum is back from a torn Achilles and Markkanen is projected under 50 games. Two rookies (Cameron Boozer, Caleb Wilson) are stand-ins, the biggest unknown on any roster.",
        vs_me="One of your easiest. You win REB, AST, BLK and FG%; they win ST."),
    "Gökhan's Groovy Team": dict(
        identity="All in on bigs (Towns, Kessler, Clingan, Zion, Diabaté) plus Flagg and Ausar Thompson. Best in FG%, REB and TO, second in BLK, last in FT%, 3PTM, PTS and AST.",
        key_players="Karl-Anthony Towns, Donovan Clingan, Kon Knueppel, Walker Kessler, Cooper Flagg, Zion Williamson",
        risks="Two rookies (Darryn Peterson, Yaxel Lendeborg) are stand-ins. Kon Knueppel has a hamstring injury to start the season.",
        vs_me="Your easiest. Their four strengths include FG% and TO, which you rarely win anyway, while your strengths (FT%, 3PTM, PTS, AST) are their four weakest. ST decides most weeks."),
}


def main():
    runs = {k: json.loads((ROOT / v).read_text(encoding="utf-8")) for k, v in RUNS.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    cats = runs["half"]["cats"]

    # league: team x fill
    league = []
    for fill, d in runs.items():
        own = {t["name"]: t["means"]["G"] for t in runs["none"]["teams"]}   # games of the drafted players alone
        own_rank = {n: i + 1 for i, n in enumerate(sorted(own, key=lambda n: -own[n]))}
        order = sorted(d["teams"], key=lambda t: -t["exp_cats_vs_field"])
        for pr, t in enumerate(order, 1):
            row = {"team": t["name"], "short": SHORT[t["name"]], "fill": fill, "power_rank": pr,
                   "exp_cats": round(t["exp_cats_vs_field"], 2), "p_week": round(t["p_week_vs_field"], 3),
                   "own_games": round(own[t["name"]], 1), "own_games_rank": own_rank[t["name"]],
                   "slot": t["slot"], "is_me": t["name"] == ME}
            for c in cats:
                row[f"rank_{CAT_KEYS[c]}"] = t["rank"][c]
                row[f"win_{CAT_KEYS[c]}"] = round(t["cat_win"][c], 3)
            league.append(row)

    # my matchups: opponent x fill
    matchups = []
    span = {o: [runs[f]["my_matchups"][o]["exp_cats"] for f in runs] for o in runs["half"]["my_matchups"]}
    for fill, d in runs.items():
        order = sorted(d["my_matchups"].items(), key=lambda kv: kv[1]["exp_cats"])
        for tr, (opp, m) in enumerate(order, 1):
            row = {"opponent": opp, "short": SHORT[opp], "fill": fill, "tough_rank": tr,
                   "my_cats": round(m["exp_cats"], 2), "their_cats": round(9 - m["exp_cats"], 2),
                   "p_week": round(m["p_week"], 3), "low": round(min(span[opp]), 2), "high": round(max(span[opp]), 2)}
            for c in cats:
                row[f"p_{CAT_KEYS[c]}"] = round(m["per"][c], 3)
            matchups.append(row)

    # head-to-head grid
    grid = []
    for fill, d in runs.items():
        names = d["matrix"]["teams"]
        for i, a in enumerate(names):
            for j, b in enumerate(names):
                if i != j:
                    grid.append({"team": a, "opponent": b, "fill": fill, "exp_cats": round(d["matrix"]["exp_cats"][i][j], 2)})

    scouting = [{"team": t["name"], "short": SHORT[t["name"]], "slot": t["slot"], **NOTES[t["name"]]}
                for t in sorted(runs["half"]["teams"], key=lambda t: t["slot"])]

    rosters = []
    for t in runs["half"]["teams"]:
        for r in t["roster"]:
            flag = ("On IL" if r.get("il") else "Added after draft" if r.get("added") else
                    "Rookie stand-in" if r["note"].startswith("rookie") else
                    "Waived, replaced by a waiver pickup" if r["note"].startswith("released") else
                    "Minutes trimmed" if r["note"].startswith("minutes") else "")
            if r["inj"] and not r.get("il"):
                flag = (flag + "; " if flag else "") + r["inj"]
            rosters.append({"team": t["name"], "player": r["name"], "nba": r["nba"], "pos": "/".join(r["pos"]),
                            "pick": r["pick"], "gp": r["gp"], "mpg": r["mpg"], "value": r["value"], "flag": flag})

    moves = []
    for fill, d in runs.items():
        others = sorted(t["exp_cats_vs_field"] for t in d["teams"] if t["name"] != ME)
        mine = next(t for t in d["teams"] if t["name"] == ME)
        rows = [("Current roster", mine["exp_cats_vs_field"], mine["p_week_vs_field"], "Robinson added, Ingram on IL")]
        for v in d["variants"]:
            rows.append((v["label"], v["exp_cats_vs_field"], v["p_week_vs_field"], v["spec"].replace(";", ", ").replace("+", "add ").replace("-", "drop ")))
        for label, e, pw, detail in rows:
            moves.append({"label": label, "fill": fill, "exp_cats": round(e, 2), "p_week": round(pw, 3),
                          "league_rank": 1 + sum(1 for o in others if o > e), "detail": detail})

    fa = []
    for f in runs["half"]["free_agents"]["list"][:15]:
        g = f["gains"]
        fa.append({"player": f["name"], "nba": f["nba"], "pos": "/".join(f["pos"]), "gp": f["gp"], "mpg": f["mpg"],
                   "games_last3": " / ".join(str(x) for x in f["games_hist"]),
                   "gain_kgeorge": round(g["Kyshawn George"], 3), "gain_carter": round(g["Wendell Carter Jr."], 3),
                   "gain_poeltl": round(g["Jakob Poeltl"], 3), "best_drop": f["replace"],
                   "note": "; ".join(x for x in [f.get("note", ""), f["inj"]] if x)})

    settings = [
        {"key": "weeks", "value": runs["half"]["weeks_simulated"], "label": "Simulated weeks per run"},
        {"key": "teams", "value": len(runs["half"]["teams"]), "label": "Teams"},
        {"key": "rookies", "value": sum(1 for r in rosters if r["flag"].startswith("Rookie")), "label": "Unprojected rookies given stand-ins"},
        {"key": "adds", "value": 3, "label": "Adds per week (league rule)"},
        {"key": "il", "value": 3, "label": "IL slots (league rule)"},
    ]

    files = {"league.json": league, "matchups.json": matchups, "grid.json": grid, "scouting.json": scouting,
             "rosters.json": rosters, "moves.json": moves, "free_agents.json": fa, "settings.json": settings}
    for name, rows in files.items():
        (OUT / name).write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{name}: {len(rows)} rows, {(OUT / name).stat().st_size // 1024 + 1} KB")


if __name__ == "__main__":
    main()
