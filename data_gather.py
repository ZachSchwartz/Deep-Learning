import requests
import time
import sqlite3
import json
import threading

match_list_key = "api_key=" + "RGAPI-cb0141a9-b92a-4104-80aa-9ca716a43b9a" # api used for the match list function
store_matches_key = "?api_key=" + "RGAPI-cb0141a9-b92a-4104-80aa-9ca716a43b9a" # api used for the store_matches function
api_key = "/ids?api_key=" + "RGAPI-cb0141a9-b92a-4104-80aa-9ca716a43b9a" # api string used everywhere else
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
    "americas": ["na1"],#, "br1", "la1", "la2"],
    #"asia": ["jp1"],#, "kr"],
    #"europe": ["eun1"],#, "euw1", "ru", "tr1"],
    #"sea": ["oc1"]#, "ph2", "sg2", "th2", "tw2", "vn2"],
}
db_file_path = "player_database.db"
match_file_path = "match_database.db"


def get_all_players():
    league_list = ["challenger", "grandmaster", "master"]
    player_conn = sqlite3.connect(db_file_path)
    player_cursor = player_conn.cursor() # create connection to database
    for league in league_list:
        for region in region_list: # loop through every ranked league, in each region
            request = requests.get(
                "https://"
                + region
                + ".api.riotgames.com/lol/league/v4/"
                + league
                + "leagues/by-queue/RANKED_SOLO_5x5"
                + api_key
            )
            if request.status_code == 200: # If the request is successful, input basic info about the user
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
                except Exception as e: # Except statement in case of error
                    print("Error processing API response:", e)
            elif request.status_code == 429: # Should I get rate limited, the program will wait to try to request info again
                print(region, league)
                time.sleep(120)


def get_puuids_by_region(region):
    region_conn = sqlite3.connect(db_file_path)
    region_cursor = region_conn.cursor()
    region_cursor.execute("SELECT summonerId FROM players WHERE region = ?", (region,)) # create list of every summonerid, then loop through the list
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
        if request.status_code == 200: # if successful, find the matching puuid for the given summoner id
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
    for region in region_list: # creates a unique thread for each region, then calls the puuid finder
        thread = threading.Thread(target=get_puuids_by_region, args=(region,)) # Using threading makes this function run significantly faster
        threads.append(thread)
        thread.start()
        print("new_thread created")

    for thread in threads: # ensures the main thread waits for all threads to finish
        thread.join()


def get_matches_played(continent, regions):
    continent_conn = sqlite3.connect(db_file_path)
    continent_cursor = continent_conn.cursor()

    for region in regions: # loop through all regions within the given continent
        continent_cursor.execute(
            "SELECT puuid FROM players WHERE region = ?", (region,)
        )
        puuids = [row[0] for row in continent_cursor.fetchall()] # find all puuids for the given region
        index = 0 # tracks where in the puuids the function is
        match_count = 0 # This variable tracks where to begin the search in a players history
        repeat_matches = set()
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
                    if len(matches) == 0:
                        index += 1
                        continue
                    for match in matches:
                        repeat_matches.add(match)
                    match_count += 100
                except Exception as e:
                    print("Error processing API response:", e)
            elif request.status_code == 429:
                print("sleeping" + continent + region + str(index))
                time.sleep(120)
            else:
                print(request.status_code)
        continent_cursor.execute(
                        """
                                UPDATE players
                                SET matches = ?
                                WHERE puuid = ?
                            """,
                        (json.dumps(list(repeat_matches)), puuids[0]),
                    )
        continent_conn.commit()


def call_match_list(continents_dictionary):
    threads = []
    for continent, regions in continents_dictionary.items():
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

    for thread in threads:
        thread.join()




def store_matches(continent, regions):
    player_conn = sqlite3.connect(db_file_path)
    player_cursor = player_conn.cursor()
    match_conn = sqlite3.connect(match_file_path)
    match_cursor = player_conn.cursor()

    for region in regions:
        player_cursor.execute(
            "SELECT matches FROM players WHERE region = ?", (region,)
        )
        matches = [row[0] for row in player_cursor.fetchall()] # the match ids are stored as a list with one element, a giant string
        matches = [match[2:-2] for match in matches[0].split()] # this line splits this string into a list that can be looped through
        match_index = 0 # index for overall match list
        while match_index < len(matches):
                request = requests.get(
                    "https://"
                    + continent
                    + ".api.riotgames.com/lol/match/v5/matches/"
                    + matches[match_index]
                    + store_matches_key
                )
                if request.status_code == 200:
                    try:
                        match_data = json.loads(request.text)
                        
                        info = match_data["info"]
                        
                        participant = info["participants"]
                        
                        team = info["teams"]
                        blue_objectives = team[0]["objectives"]
                        red_objectives = team[1]["objectives"]
                        match_cursor.execute(
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
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                info["gameId"],
                                info["gameDuration"],
                                info["participants"],
                                info["gameVersion"],
                                [int(blue_objectives["baron"]["first"]), int(red_objectives["baron"]["first"])],
                                [blue_objectives["baron"]["kills"], red_objectives["baron"]["kills"]],
                                [int(blue_objectives["champion"]["first"]), int(red_objectives["champion"]["first"])],
                                [blue_objectives["champion"]["kills"], red_objectives["champion"]["kills"]],
                                [int(blue_objectives["dragon"]["first"]), int(red_objectives["dragon"]["first"])],
                                [blue_objectives["dragon"]["kills"], red_objectives["dragon"]["kills"]],
                                [int(blue_objectives["inhibitor"]["first"]), int(red_objectives["inhibitor"]["first"])],
                                [blue_objectives["inhibitor"]["kills"], red_objectives["inhibitor"]["kills"]],
                                [int(blue_objectives["riftHerald"]["first"]), int(red_objectives["riftHerald"]["first"])],
                                [blue_objectives["riftHerald"]["kills"], red_objectives["riftHerald"]["kills"]],
                                [int(blue_objectives["tower"]["first"]), int(red_objectives["tower"]["first"])],
                                [blue_objectives["tower"]["kills"], red_objectives["tower"]["kills"]],
                                int(team["win"]),
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
                                int(participant["firstBloodAssist"]),
                                int(participant["firstBloodKill"]),
                                int(participant["firstTowerAssist"]),
                                int(participant["firstTowerKill"]),
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
                            ),
                        )
                        match_conn.commit()
                        match_index += 1
                    except Exception as e:
                        print("Error processing API response:", e)
                elif request.status_code == 429:
                    print("sleeping" + continent + region + match_index)
                    time.sleep(120)
                else:
                    print(request.status_code)


def call_store_matches():
    threads = []
    for continent, regions in continents_dictionary.items():
        thread = threading.Thread(
            target=store_matches,
            args=(
                continent,
                regions,
            ),
        )
        threads.append(thread)
        thread.start()
        print("new_thread created")

    for thread in threads:
        thread.join()

#call_match_list(continents_dictionary)
#call_store_matches()
        