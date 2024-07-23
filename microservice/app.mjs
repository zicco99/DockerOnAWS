import express from "express";
import connectToDatabase from "./db.mjs";

const app = express();

app.get("/", async (req, res) => {
    res.send("<h2>Hi there!</h2>")
})

await connectToDatabase();

app.listen(80, () => {
    console.log("Listening on port 80 - http://localhost:80");
})