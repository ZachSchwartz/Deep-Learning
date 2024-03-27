import requests
import time
import sqlite3
import json
import threading

match_list_key = "api_key=" + "RGAPI-2e63df17-6450-406c-8070-3c9bf17aaf3b"
api_key = "/ids?api_key=" + "RGAPI-2e63df17-6450-406c-8070-3c9bf17aaf3b"
region_list = [
    "br1",
    "eun1",
    "euw1",
    "jp1",
    "kr",
    "la1",
    "la2",
    "na1",
    "oc1",
    "ph2",
    "ru",
    "sg2",
    "th2",
    "tr1",
    "tw2",
    "vn2",
]
continents_dictionary = {
    "americas": ["na1", "br1", "la1", "la2"],
    "asia": ["jp1", "kr"],
    "europe": ["eun1", "euw1", "ru", "tr1"],
    "sea": ["oc1", "ph2", "sg2", "th2", "tw2", "vn2"],
}
db_file_path = "player_database.db"
match_file_path = "match_database.db"


def get_all_players():
    league_list = ["challenger", "grandmaster", "master"]
    player_conn = sqlite3.connect(db_file_path)
    player_cursor = player_conn.cursor()
    for league in league_list:
        for region in region_list:
            request = requests.get(
                "https://"
                + region
                + ".api.riotgames.com/lol/league/v4/"
                + league
                + "leagues/by-queue/RANKED_SOLO_5x5"
                + api_key
            )
            if request.status_code == 200:
                try:
                    users = json.loads(request.text)
                    for record in users["entries"]:
                        player_cursor.execute(
                            """
                            INSERT INTO players (summonerName, summonerId, rank, leaguePoints, region)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                record["summonerName"],
                                record["summonerId"],
                                league,
                                record["leaguePoints"],
                                region,
                            ),
                        )
                        player_conn.commit()
                except Exception as e:
                    print("Error processing API response:", e)
            elif request.status_code == 429:
                print(region, league)
                time.sleep(120)


def get_puuids_by_region(region):
    # Create a new SQLite connection and cursor for this thread
    region_conn = sqlite3.connect(db_file_path)
    region_cursor = region_conn.cursor()
    region_cursor.execute("SELECT summonerId FROM players WHERE region = ?", (region,))
    summoner_ids = [row[0] for row in region_cursor.fetchall()]
    index = 0
    while index < len(summoner_ids):
        request = requests.get(
            "https://"
            + region
            + ".api.riotgames.com/lol/summoner/v4/summoners/"
            + summoner_ids[index]
            + api_key
        )
        if request.status_code == 200:
            try:
                user = json.loads(request.text)
                region_cursor.execute(
                    """
                            UPDATE players
                            SET summonerLevel = ?, puuid = ?
                            WHERE summonerId = ?
                        """,
                    (user["summonerLevel"], user["puuid"], summoner_ids[index]),
                )
                region_conn.commit()
                index += 1
            except Exception as e:
                print("Error processing API response:", e)
        elif request.status_code == 429:
            print("sleeping")
            time.sleep(120)


def call_puuids(region_list):
    threads = []
    for region in region_list:
        # Create a new database connection for each region
        thread = threading.Thread(target=get_puuids_by_region, args=(region,))
        threads.append(thread)
        thread.start()
        print("new_thread created")

        # Wait for all threads to finish
    for thread in threads:
        thread.join()












def get_matches_played(continent, regions):
    continent_conn = sqlite3.connect(db_file_path)
    continent_cursor = continent_conn.cursor()

    for region in regions:
        continent_cursor.execute(
            "SELECT puuid FROM players WHERE region = ?", (region,)
        )
        puuids = [row[0] for row in continent_cursor.fetchall()]
        index = 0
        match_count = 0
        repeat_matches = []
        while index < len(puuids):
            request = requests.get(
                "https://"
                + continent
                + ".api.riotgames.com/lol/match/v5/matches/by-puuid/"
                + puuids[index]
                + "/ids?startTime=16417728&type=ranked&start="
                + str(match_count)
                + "&count=100&"
                + match_list_key
            )
            if request.status_code == 200:
                try:
                    matches = json.loads(request.text)
                    repeat_index = 0
                    while repeat_index < len(matches):
                        if matches[repeat_index] not in repeat_matches:
                            repeat_matches.append(matches[repeat_index])
                        else:
                            del matches[repeat_index]
                            repeat_index -= 1  # Decrement index to account for removed item
                        repeat_index += 1  # Move to the next item in the list
                    continent_cursor.execute(
                        """
                                UPDATE players
                                SET matches = ?
                                WHERE puuid = ?
                            """,
                        (json.dumps(matches), puuids[index]),
                    )
                    continent_conn.commit()
                    match_count += 100
                except Exception as e:
                    print("Error processing API response:", e)
            elif request.status_code == 404:
                match_count = 0
                index += 1
            elif request.status_code == 429:
                print("sleeping" + continent + region + index)
                time.sleep(120)
            else:
                print(request.status_code)


def call_match_list(continents_dictionary):
    threads = []
    for continent, regions in continents_dictionary.items():
        # Create a new database connection for each region
        thread = threading.Thread(
            target=get_matches_played,
            args=(
                continent,
                regions,
            ),
        )
        threads.append(thread)
        thread.start()
        print("new_thread created")

        # Wait for all threads to finish
    for thread in threads:
        thread.join()


call_match_list(continents_dictionary)




def store_matches(continent, regions):
    continent_conn = sqlite3.connect(match_file_path)
    continent_cursor = continent_conn.cursor()

    for region in regions:
        continent_cursor.execute(
            "SELECT matches FROM players WHERE region = ?", (region,)
        )
        matches = [row[0] for row in continent_cursor.fetchall()]
        match_index = 0
        batch_index = 0
        while match_index < len(matches):
            while batch_index < len(matches[match_index]):
                request = requests.get(
                    "https://"
                    + continent
                    + ".api.riotgames.com/lol/match/v5/matches/"
                    + matches[match_index][batch_index]
                    + api_key
                )
                if request.status_code == 200:
                    try:
                        match_data = json.loads(request.text)
                        print(matches)
                        info = match_data["info"]
                        participant = info["participants"]
                        team = info["teams"]
                        objectives = team["objectives"]
                        continent_cursor.execute(
                            """
                            INSERT INTO matches (
                                gameId,
                                gameDuration,
                                participants,
                                gameVersion,
                                tier,
                                rank,
                                teamBaronKills,
                                teamBaronFirst,
                                teamChampionKills,
                                teamChampionFirst,
                                teamDragonKills,
                                teamDragonFirst,
                                teamInhibitorKills,
                                teamInhibitorFirst,
                                teamRiftHeraldKills,
                                teamRiftHeraldFirst,
                                teamTurretKills,
                                teamTurretFirst,
                                teamwin,
                                assists,
                                baronKills,
                                champExperience,
                                champLevel,
                                championId,
                                championName,
                                damageDealtToBuildings,
                                damageDealtToObjectives,
                                damageDealtToTurrets,
                                damageSelfMitigated,
                                deaths,
                                detectorWardsPlaced,
                                doubleKills,
                                dragonKills,
                                firstBloodAssist,
                                firstBloodKill,
                                firstTowerAssist,
                                firstTowerKill,
                                goldEarned,
                                goldSpent,
                                inhibitorKills,
                                inhibitorTakedowns,
                                killingSprees,
                                kills,
                                largestKillingSpree,
                                largestMultiKill,
                                objectivesStolen,
                                objectivesStolenAssists,
                                participantId,
                                pentaKills,
                                puuid,
                                quadraKills,
                                riotIdName,
                                riotIdTagline,
                                sightWardsBoughtInGame,
                                summonerId,
                                summonerLevel,
                                summonerName,
                                teamId,
                                teamPosition,
                                timeCCingOthers,
                                totalDamageDealt,
                                totalDamageDealtToChampions,
                                totalDamageShieldedOnTeammates,
                                totalDamageTaken,
                                totalHeal,
                                totalHealsOnTeammates,
                                totalMinionsKilled,
                                totalTimeSpentDead,
                                tripleKills,
                                turretKills,
                                turretTakedowns,
                                visionScore,
                                visionWardsBoughtInGame,
                                wardsKilled,
                                wardsPlaced,
                                win
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,(
                                info["gameId"],
                                info["gameDuration"],
                                info["participants"],
                                info["gameVersion"],
                                objectives["baron"]["first"],
                                objectives["baron"]["kills"],
                                objectives["champion"]["first"],
                                objectives["champion"]["kills"],
                                objectives["dragon"]["first"],
                                objectives["dragon"]["kills"],
                                objectives["inhibitor"]["first"],
                                objectives["inhibitor"]["kills"],
                                objectives["riftHerald"]["first"],
                                objectives["riftHerald"]["kills"],
                                objectives["tower"]["first"],
                                objectives["tower"]["kills"],
                                team["win"],
                                participant["assists"],
                                participant["baronKills"],
                                participant["champExperience"],
                                participant["champLevel"],
                                participant["championId"],
                                participant["championName"],
                                participant["damageDealtToBuildings"],
                                participant["damageDealtToObjectives"],
                                participant["damageDealtToTurrets"],
                                participant["damageSelfMitigated"],
                                participant["deaths"],
                                participant["detectorWardsPlaced"],
                                participant["doubleKills"],
                                participant["dragonKills"],
                                participant["firstBloodAssist"],
                                participant["firstBloodKill"],
                                participant["firstTowerAssist"],
                                participant["firstTowerKill"],
                                participant["goldEarned"],
                                participant["goldSpent"],
                                participant["inhibitorKills"],
                                participant["inhibitorTakedowns"],
                                participant["killingSprees"],
                                participant["kills"],
                                participant["largestKillingSpree"],
                                participant["largestMultiKill"],
                                participant["objectivesStolen"],
                                participant["objectivesStolenAssists"],
                                participant["participantId"],
                                participant["pentaKills"],
                                participant["puuid"],
                                participant["quadraKills"],
                                participant["riotIdName"],
                                participant["riotIdTagline"],
                                participant["sightWardsBoughtInGame"],
                                participant["summonerId"],
                                participant["summonerLevel"],
                                participant["summonerName"],
                                participant["teamId"],
                                participant["teamPosition"],
                                participant["timeCCingOthers"],
                                participant["totalDamageDealt"],
                                participant["totalDamageDealtToChampions"],
                                participant["totalDamageShieldedOnTeammates"],
                                participant["totalDamageTaken"],
                                participant["totalHeal"],
                                participant["totalHealsOnTeammates"],
                                participant["totalMinionsKilled"],
                                participant["totalTimeSpentDead"],
                                participant["tripleKills"],
                                participant["turretKills"],
                                participant["turretTakedowns"],
                                participant["visionScore"],
                                participant["visionWardsBoughtInGame"],
                                participant["wardsKilled"],
                                participant["wardsPlaced"],
                                participant["win"],
                            )
                        )
                        continent_conn.commit()
                        batch_index += 1
                    except Exception as e:
                        print("Error processing API response:", e)
                elif request.status_code == 429:
                    print("sleeping" + continent + region + match_index)
                    time.sleep(120)
                else:
                    print(request.status_code)
            batch_index = 0
            match_index += 1


def call_store_matches(continents_dictionary):
    threads = []
    for continent, regions in continents_dictionary.items():
        # Create a new database connection for each region
        thread = threading.Thread(
            target=get_matches_played,
            args=(
                continent,
                regions,
            ),
        )
        threads.append(thread)
        thread.start()
        print("new_thread created")

        # Wait for all threads to finish
    for thread in threads:
        thread.join()
