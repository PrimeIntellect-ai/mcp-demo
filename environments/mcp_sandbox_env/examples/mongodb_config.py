SYSTEM_PROMPT = """You are a database assistant with access to MongoDB tools.

Your task is to execute MongoDB queries using the provided tools. You MUST use the MongoDB tools to:
1. Connect to and query the database
2. Execute aggregation pipelines
3. Retrieve and analyze data

Use tool calls to execute the queries - do not just describe what the results should be.
Continue using tools until the task is fully complete."""

MONGODB_CONFIG = {
    "name": "mongodb",
    "docker_image": "mongo:latest",
    "server_start_cmd": "npx -y mongodb-mcp-server@latest --transport http --httpHost=0.0.0.0 --httpPort=3001 --readOnly",
    "server_env": {
        "MDB_MCP_CONNECTION_STRING": "mongodb://localhost:27017/sample_mflix",
    },
    "pre_install_cmds": [
        # Start MongoDB
        "mkdir -p /data/db",
        "mongod --fork --logpath /var/log/mongodb.log --dbpath /data/db",
        "sleep 3",
        # Install Node.js
        "apt-get update && apt-get install -y curl git xz-utils",
        "curl -fsSL https://nodejs.org/dist/v22.20.0/node-v22.20.0-linux-x64.tar.xz -o /tmp/node.tar.xz",
        "tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1",
        # Load sample data
        "git clone https://github.com/neelabalan/mongodb-sample-dataset.git /tmp/dataset",
        "mongoimport --db sample_mflix --collection movies --file /tmp/dataset/sample_mflix/movies.json",
        "mongoimport --db sample_mflix --collection comments --file /tmp/dataset/sample_mflix/comments.json",
        "mongoimport --db sample_mflix --collection theaters --file /tmp/dataset/sample_mflix/theaters.json",
    ],
    "mcp_port": 3001,
    "mcp_path": "/mcp",
    "dataset": {
        "question": [
            "Count the total number of movies in the sample_mflix database. Run this command: db.movies.countDocuments()",
            "Display the title and awards of the five oldest released movies in the sample_mflix database. Run this command: db.movies.find({ }, { title: 1, awards: 1, _id: 0 }).sort({ year: 1 }).limit(5)",
            'Display the five movies that have won the most number of awards in the sample_mflix database. Run this command: db.movies.aggregate( [ { $group: {_id: "", num: { $max:"$awards.wins" } } } ] )',
            'Count the number of short documentaries in the sample_mflix database. Run this command: db.movies.find({ genres: { $all: ["Documentary", "Short"] } }).count()',
            'Display all titles of movies that have won more than 3 awards and belong to the Adventure genre in the sample_mflix database. Run this command: db.movies.find({ "genres": "Adventure", "awards.wins": { $gt: 3 } }, { "title": 1, "_id": 0 })',
            'For each year, display the title of the movie that has won the highest number of awards in the sample_mflix database. Run this command: db.movies.aggregate([ { $unwind: "$awards" }, { $group: { _id: { year: "$year", title: "$title" }, maxWins: { $max: "$awards.wins" } } }, { $group: { _id: "$_id.year", maxWins: { $max: "$maxWins" }, topMovie: { $first: "$_id.title" } } }, { $project: { _id: 0, year: "$_id", topMovie: 1, maxWins: 1 } } ])',
            'Display the 5 most recent comments from the comments collection in the sample_mflix database. Run this command: db.comments.find().sort({ "date": -1 }).limit(5)',
            'Display the name of the user who has made the highest number of comments in the sample_mflix database. Run this command: db.comments.aggregate([ { $group: { _id: "$name", totalComments: { $sum: 1 } } }, { $sort: { totalComments: -1 } }, { $limit: 1 } ])',
            'Display movies that have an IMDB rating less than 6 but have won at least one award in the sample_mflix database. Run this command: db.movies.aggregate([ { $match: { "imdb.rating": { $lt: 6 }, "awards.wins": { $gt: 0 } } } ])',
            'Display the average number of awards won for each genre/category in the sample_mflix database. Run this command: db.movies.aggregate([ { $unwind: "$genres" }, { $group: { _id: "$genres", avgAwards: { $avg: "$awards.wins" } } }, { $addFields: { avgAwards: { $round: ["$avgAwards", 0] } } } ])',
        ],
        "answer": [
            "21349",
            "TODO",
            "TODO",
            "TODO",
            "TODO",
            "TODO",
            "TODO",
            "TODO",
            "TODO",
            "TODO",
        ],
    },
    "system_prompt": SYSTEM_PROMPT,
}
