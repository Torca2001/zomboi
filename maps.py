from datetime import datetime
import discord
from discord.ext import commands
import glob
import os
from pathlib import Path
import PIL.ImageDraw as ImageDraw
import PIL.Image as Image
import xml.etree.ElementTree as ET

# Taken from ISMapDefinitions.lua
colours = {
    "default": (219, 215, 192),
    "forest": (189, 197, 163),
    "river": (59, 141, 149),
    "trail": (185, 122, 87),
    "tertiary": (171, 158, 143),
    "secondary": (134, 125, 113),
    "primary": (134, 125, 113),
    "*": (200, 191, 231),
    "yes": (210, 158, 105),
    "Residential": (210, 158, 105),
    "CommunityServices": (139, 117, 235),
    "Hospitality": (127, 206, 225),
    "Industrial": (56, 54, 53),
    "Medical": (229, 128, 151),
    "RestaurantsAndEntertainment": (245, 225, 60),
    "RetailAndCommercial": (184, 205, 84),
    "no": (255, 100, 100),
    "wood": (87, 33, 0),
    "gravel": (135, 135, 135),
}

pathsToTry = [
    "steam/steamapps/common/Project Zomboid Dedicated Server/media/maps",
    "steam/steamapps/common/ProjectZomboid/media/maps",
]


class MapHandler(commands.Cog):
    """Class which handles generation of maps"""

    def __init__(self, bot):
        self.bot = bot
        # Validate the maps path
        self.mapsPath = os.getenv("MAPS_PATH")
        if self.mapsPath is None or len(self.mapsPath) == 0:
            for path in pathsToTry:
                tryPath = Path.home().joinpath(path)
                if tryPath.exists():
                    self.mapsPath = str(tryPath)
                    break
        if self.mapsPath is None or len(self.mapsPath) == 0 or not Path(self.mapsPath).is_dir():
            self.bot.log.error(f"Map path {self.mapsPath} not found and/or no suitable default")
        else:
            self.bot.log.info(f"Maps path: {self.mapsPath}")

        self.mapName = os.getenv("MAP_NAME")
        if self.mapName is None or len(self.mapName) == 0:
            self.mapName = "Muldraugh, KY"
        elif not Path(self.mapsPath + (f"/{self.mapName}/")).is_dir():
            self.bot.log.error(f"Map name {self.mapName} not found, check map path or map name")
            self.mapName = "Muldraugh, KY"

        self.loadWorkshopMaps()


    def loadWorkshopMaps(self):
        # load workshop maps and check they match for the map
        workshopMaps = os.getenv("WORKSHOP_PATH")
        files = []

        mainForestMap = self.mapsPath + (f"/{self.mapName}/worldmap-forest.xml")
        if os.path.isfile(mainForestMap):
            files.append(mainForestMap)
        mainMap = self.mapsPath + (f"/{self.mapName}/worldmap.xml")
        if os.path.isfile(mainMap):
            files.append(mainMap)

        if workshopMaps is not None and len(workshopMaps) > 0:
            mapsInfo = glob.glob(workshopMaps + "/**/map.info", recursive=True)
            for mapInfo in mapsInfo:
                try:
                    with open(mapInfo, "r", encoding="utf-8", errors="replace") as f:
                        fileContent = f.read()

                        # Check if this mod file is for the map we are using
                        if f"lots={self.mapName}" in fileContent:
                            worldForest = mapInfo.replace("map.info", "worldmap-forest.xml")
                            if os.path.isfile(worldForest):
                                files.append(worldForest)
                            worldMap = mapInfo.replace("map.info", "worldmap.xml")
                            if os.path.isfile(worldMap):
                                files.append(worldMap)
                except Exception as e:
                    self.bot.log.error(f"Error reading map info {mapInfo}: {e}")
                    
        #Parse each map xml and store for use later
        for file in files:
            try:
                tree = ET.parse(file)
                root = tree.getroot()
                self.mapTreeRoots.append(root)
            except Exception as e:
                self.bot.log.error(f"Error parsing map file {file}: {e}")

    @commands.command()
    async def location(self, ctx, name=None, mapSize = None):
        """Get the last known location of the given user"""
        if name is None:
            name = ctx.author.name
        user = self.bot.get_cog("UserHandler").getUserAuto(name)

        if user is None:
            await ctx.reply(f"User {name} not found")
            return
        
        name = user.name

        x = int(user.lastLocation[0])
        y = int(user.lastLocation[1])

        result = self.bot.get_cog("UserHandler").getDBLoc(name)
        if result is not None:
            x = result[0]
            y = result[1]

        chunkSize = 300


        mapWidth = 3
        playerSize = 2

        if mapSize is not None:
            try:
                newSize = int(mapSize)
                if newSize > 39:
                    newSize = 39
                mapWidth = newSize
            except ValueError:
                print("\nPlease only use integers")

        if (mapWidth % 2) == 0:
            mapWidth += 1
        if (mapWidth < 1):
            mapWidth = 1

        drawSize = chunkSize * mapWidth

        cellx = x // chunkSize
        celly = y // chunkSize
        posX = x % chunkSize + (mapWidth // 2) * chunkSize
        posY = y % chunkSize + (mapWidth // 2) * chunkSize

        image = Image.new("RGB", (drawSize, drawSize), colours["default"])
        draw = ImageDraw.Draw(image)

        for root in self.mapTreeRoots:
            for cell in root.findall("cell"):
                currX = int(cell.get("x"))
                currY = int(cell.get("y"))
                if ((currX + (mapWidth // 2) >= cellx and currX - (mapWidth // 2) <= cellx) and 
                    (currY + (mapWidth // 2) >= celly and currY - (mapWidth // 2) <= celly)):
                    cellOffsetX = (currX - cellx + (mapWidth // 2)) * chunkSize
                    cellOffsetY = (currY - celly + (mapWidth // 2)) * chunkSize
                    for feature in cell.findall("feature"):
                        for geometry in feature.findall("geometry"):
                            if geometry.get("type") == "Polygon":
                                for coordinates in geometry.findall("coordinates"):
                                    points = []
                                    for point in coordinates.findall("point"):
                                        points.append(
                                            (cellOffsetX + int(point.get("x")), cellOffsetY + int(point.get("y")))
                                        )
                                for properties in feature.findall("properties"):
                                    for property in properties.findall("property"):
                                        if property.get("value") not in colours:
                                            self.bot.log.info(f'Tile not recognised {property.get("value")} name: {property.get("name")}')
                                        else:
                                            draw.polygon(
                                                points, fill=colours[property.get("value")]
                                            )

            draw.polygon(
                (
                    (posX - playerSize, posY - playerSize),
                    (posX + playerSize, posY - playerSize),
                    (posX + playerSize, posY + playerSize),
                    (posX - playerSize, posY + playerSize),
                ),
                (255, 0, 0),
            )
        image.save("map.png")
        await ctx.send(
            file=discord.File("map.png"),
            content=f"{name} was last seen <t:{round(datetime.timestamp(user.lastSeen))}:R>",
        )
