import requests
import time
import sqlite3
import json
import threading
import datetime

dev_key = "RGAPI-42d505b4-1410-4a9b-b7fa-955bf98ab0a8"
api_key = "?api_key=" + "RGAPI-2e63df17-6450-406c-8070-3c9bf17aaf3b"
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
        'americas': ['na1', 'br1', 'la1', 'la2'],
        'asia': ['jp1', 'kr'],
        'europe': ['eun1', 'euw1', 'ru', 'tr1'],
        'sea': ['oc1', 'ph2', 'sg2', 'th2', 'tw2', 'vn2']
    }
db_file_path = "player_database.db"
player_conn = sqlite3.connect(db_file_path)
player_cursor = player_conn.cursor()
# player_conn.execute(
#     """
#     CREATE TABLE IF NOT EXISTS players (
#         id INTEGER PRIMARY KEY,
#         summonerid TEXT,
#         summonerLevel INTEGER,
#         summonerName TEXT,
#         rank TEXT,
#         leaguePoints INTEGER,
#         region TEXT,
#         puuid TEXT,
#         matches TEXT
#     )
# """
# )

# player_cursor.execute('PRAGMA foreign_keys=off;')
# player_cursor.execute('BEGIN TRANSACTION;')
# player_cursor.execute('ALTER TABLE players RENAME TO players_backup;')
# player_cursor.execute('''
#     CREATE TABLE players (
#         summonerid TEXT,
#         summonerLevel INTEGER,
#         summonerName TEXT,
#         rank TEXT,
#         leaguePoints INTEGER,
#         region TEXT,
#         puuid TEXT,
#         matches TEXT
#     )
# ''')
# player_cursor.execute('DROP TABLE players_backup;')
# player_cursor.execute('COMMIT;')
# player_cursor.execute('PRAGMA foreign_keys=on;')
# player_cursor.execute('''
#     DELETE FROM players
#     WHERE rowid NOT IN (
#         SELECT MIN(rowid)
#         FROM players
#         GROUP BY summonerId
#     )
# ''')

# player_conn.commit()

match_file_path = "match_database.db"
match_conn = sqlite3.connect(match_file_path)
match_cursor = match_conn.cursor()
# match_conn.execute(
#     """
#     CREATE TABLE IF NOT EXISTS matches (
#         id INTEGER PRIMARY KEY,
#         gameDuration INTEGER,
#         participants TEXT,
#         gameVersion TEXT,
#         tier TEXT,
#         rank TEXT,
#         teamBaronKills TEXT,
#         teamBaronFirst INTEGER,
#         teamChampionKills TEXT,
#         teamChampionFirst INTEGER,
#         teamDragonKills TEXT,
#         teamDragonFirst INTEGER,
#         teamInhibitorKills TEXT,
#         teamInhibitorFirst INTEGER,
#         teamRiftHeraldKills TEXT,
#         teamRifeHeraldFirst INTEGER,
#         teamTurretKills TEXT,
#         teamTurretFirst INTEGER,
#         teamwin INTEGER,
#         assists	INTEGER,	
#         baronKills	INTEGER,		
#         champExperience	INTEGER,	
#         champLevel	INTEGER,	
#         championId	INTEGER,
#         championName	TEXT	
#         damageDealtToBuildings	INTEGER,	
#         damageDealtToObjectives	INTEGER,	
#         damageDealtToTurrets	INTEGER,	
#         damageSelfMitigated	INTEGER,	
#         deaths	INTEGER,	
#         detectorWardsPlaced	INTEGER,	
#         doubleKills	INTEGER,	
#         dragonKills	INTEGER,	
#         firstBloodAssist	INTEGER,	
#         firstBloodKill	INTEGER,	
#         firstTowerAssist	INTEGER,	
#         firstTowerKill	INTEGER,	
#         goldEarned	INTEGER,	
#         goldSpent	INTEGER,	
#         inhibitorKills	INTEGER,	
#         inhibitorTakedowns	INTEGER,	
#         killingSprees	INTEGER,	
#         kills	INTEGER,	
#         largestKillingSpree	INTEGER,	
#         largestMultiKill	INTEGER,		
#         objectivesStolen	INTEGER,	
#         objectivesStolenAssists	INTEGER,	
#         participantId	INTEGER,	
#         pentaKills	INTEGER,		
#         puuid	TEXT	
#         quadraKills	INTEGER,	
#         riotIdName	TEXT	
#         riotIdTagline	TEXT	
#         sightWardsBoughtInGame	INTEGER,	
#         summonerId	TEXT	
#         summonerLevel	INTEGER,	
#         summonerName	TEXT	
#         teamId	INTEGER,	
#         teamPosition	TEXT	
#         timeCCingOthers	INTEGER,	
#         totalDamageDealt	INTEGER,	
#         totalDamageDealtToChampions	INTEGER,	
#         totalDamageShieldedOnTeammates	INTEGER,	
#         totalDamageTaken	INTEGER,	
#         totalHeal	INTEGER,	
#         totalHealsOnTeammates	INTEGER,	
#         totalMinionsKilled	INTEGER,	
#         totalTimeSpentDead	INTEGER,	
#         tripleKills	INTEGER,	
#         turretKills	INTEGER,	
#         turretTakedowns	INTEGER,	
#         visionScore	INTEGER,	
#         visionWardsBoughtInGame	INTEGER,	
#         wardsKilled	INTEGER,	
#         wardsPlaced	INTEGER,	
#         win	INTEGER
#     )
# """
# )


def get_all_players():
    league_list = ["challenger", "grandmaster", "master"]
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
                                region
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
    region_cursor.execute('SELECT summonerId FROM players WHERE region = ?', (region,))
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
                        region_cursor.execute('''
                            UPDATE players
                            SET summonerLevel = ?, puuid = ?
                            WHERE summonerId = ?
                        ''', (user['summonerLevel'], user['puuid'], summoner_ids[index]))
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
        print('new_thread created')

        # Wait for all threads to finish
    for thread in threads:
        thread.join()

def get_matches_played(continent, regions, date):
    continent_conn = sqlite3.connect(db_file_path)
    continent_cursor = continent_conn.cursor()

    for region in regions:
        continent_cursor.execute('SELECT puuid FROM players WHERE region = ?', (region,))
        puuids = [row[0] for row in continent_cursor.fetchall()]
        index = 0
        match_count = 0

        while index < len(puuids):
                request = requests.get(
                    "https://"
                    + continent
                    + ".api.riotgames.com/lol/match/v5/matches/by-puuid/"
                    + puuids[index]
                    +'/ids?startTime=' + str(date.timestamp()) + '&type=ranked&start=' + str(match_count) + '&count=100'
                    + api_key
                )
                if request.status_code == 200:
                    try:
                            matches = json.loads(request.text)
                            continent_cursor.execute('''
                                UPDATE players
                                SET matches = ?
                                WHERE puuid = ?
                            ''', (matches, puuids[index]))
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


def call_matches(continents_dictionary):
    threads = []
    date = datetime.datetime(2022, 1, 10, tzinfo=datetime.timezone.utc)
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    for continent, regions in continents_dictionary.items():
        # Create a new database connection for each region
        thread = threading.Thread(target=get_matches_played, args=(continent, regions, date))
        threads.append(thread)
        thread.start()
        print('new_thread created')

        # Wait for all threads to finish
    for thread in threads:
        thread.join()

call_matches(continents_dictionary)