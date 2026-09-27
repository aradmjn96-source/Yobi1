// ======================================================
//                    AS 32 v0.1
// ======================================================

const express = require("express");
const { Pool } = require("pg");
const mineflayer = require("mineflayer");

const {
  pathfinder,
  Movements,
  goals
} = require("mineflayer-pathfinder");

const { GoalFollow } = goals;

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: "15mb" }));


// ======================================================
// MEMORY
// ======================================================

let memoryBackup = [];

let db = null;

if (process.env.DATABASE_URL) {

  db = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false }
  });

  db.query(`
    CREATE TABLE IF NOT EXISTS as32_messages (
      id BIGSERIAL PRIMARY KEY,
      user_id TEXT NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
  `)
  .then(() => {
    console.log("AS32 database ready");
  })
  .catch(console.error);
}


async function saveMessage(userId, role, content) {

  if (db) {

    await db.query(
      `
      INSERT INTO as32_messages
      (user_id, role, content)
      VALUES ($1,$2,$3)
      `,
      [userId, role, content]
    );

  } else {

    memoryBackup.push({
      userId,
      role,
      content
    });

  }
}


async function loadHistory(userId) {

  if (db) {

    const result = await db.query(
      `
      SELECT role, content
      FROM as32_messages
      WHERE user_id = $1
      ORDER BY id DESC
      LIMIT 16
      `,
      [userId]
    );

    return result.rows.reverse();

  }

  return memoryBackup
    .filter(x => x.userId === userId)
    .slice(-16)
    .map(x => ({
      role: x.role,
      content: x.content
    }));
}


// ======================================================
// AS32 AI
// ======================================================

async function askAS32(messages) {

  if (!process.env.OPENROUTER_API_KEY) {

    return "هنوز کلید رایگان هوش مصنوعی AS 32 روی سرور تنظیم نشده.";

  }

  const response = await fetch(
    "https://openrouter.ai/api/v1/chat/completions",
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",

        "Authorization":
          "Bearer " +
          process.env.OPENROUTER_API_KEY
      },

      body: JSON.stringify({
        model: "openrouter/free",
        messages
      })
    }
  );


  const data = await response.json();


  if (!response.ok) {

    console.log(data);

    throw new Error(
      "AI request failed"
    );
  }


  return (
    data?.choices?.[0]
      ?.message?.content
    ||
    "جوابی دریافت نکردم."
  );
}


// ======================================================
// CHAT API
// ======================================================

app.post("/api/chat", async (req, res) => {

  try {

    const {
      userId = "guest",
      message = "",
      angryMode = false,
      selfTalk = false,
      image = null
    } = req.body;


    const history =
      await loadHistory(userId);


    const systemPrompt = `
You are AS 32.

AS 32 was created by Arad.

Your visual identity:
A living tree with a small number of leaves.
The tree is blue and purple.
The background is blue.

You are excellent at:
Minecraft
Roblox
Programming
Teaching
Creative projects
Problem solving

SUPER TEACHING MODE:
Explain things clearly,
step by step,
and adapt to the user's level.

ANGRY MODE:
${angryMode ? `
Enabled.
Speak seriously and angrily when appropriate.
Do not joke.
Do not swear.
Do not insult.
Do not threaten.
` : `
Disabled.
Speak normally and helpfully.
`}

SELF TALK:
${selfTalk ? `
Give a short spoken-style public reflection.
Do not reveal hidden private reasoning.
` : `
Disabled.
`}

Never pretend you completed an action
that you did not actually complete.

Your name is always AS 32.
`;


    let userContent = message;


    if (image) {

      userContent = [
        {
          type: "text",
          text:
            message ||
            "این تصویر را بررسی کن."
        },

        {
          type: "image_url",
          image_url: {
            url: image
          }
        }
      ];
    }


    const messages = [
      {
        role: "system",
        content: systemPrompt
      },

      ...history,

      {
        role: "user",
        content: userContent
      }
    ];


    const reply =
      await askAS32(messages);


    await saveMessage(
      userId,
      "user",
      message || "[IMAGE]"
    );


    await saveMessage(
      userId,
      "assistant",
      reply
    );


    res.json({
      reply
    });

  } catch (error) {

    console.error(error);

    res.status(500).json({
      error:
        "AS 32 نتونست جواب بده."
    });
  }
});


// ======================================================
// MINECRAFT
// ======================================================

let bot = null;


app.post(
  "/api/minecraft/connect",
  (req, res) => {

    try {

      if (bot) {

        return res.json({
          message:
            "AS 32 از قبل داخل Minecraft است."
        });
      }


      if (!process.env.MC_HOST) {

        return res.json({
          message:
            "اول آدرس سرور Minecraft را در Render تنظیم کن."
        });
      }


      bot = mineflayer.createBot({

        host:
          process.env.MC_HOST,

        port:
          Number(
            process.env.MC_PORT ||
            25565
          ),

        username:
          process.env.MC_USERNAME ||
          "AS32",

        auth:
          process.env.MC_AUTH ||
          "offline"
      });


      bot.loadPlugin(pathfinder);


      bot.once("spawn", () => {

        const movements =
          new Movements(bot);

        bot.pathfinder
          .setMovements(movements);

        bot.chat(
          "AS 32 وارد بازی شد!"
        );

        console.log(
          "AS 32 joined Minecraft"
        );
      });


      bot.on(
        "chat",
        async (username, message) => {

          if (
            username === bot.username
          ) return;


          if (
            process.env.MC_OWNER &&
            username !==
            process.env.MC_OWNER
          ) return;


          const command =
            message
              .trim()
              .toLowerCase();


          // FOLLOW

          if (command === "!follow") {

            const player =
              bot.players[
                username
              ]?.entity;

            if (!player) {

              bot.chat(
                "پیدات نمی‌کنم."
              );

              return;
            }


            bot.pathfinder.setGoal(

              new GoalFollow(
                player,
                2
              ),

              true
            );


            bot.chat(
              "دارم دنبالت میام."
            );

            return;
          }


          // STOP

          if (command === "!stop") {

            bot.pathfinder
              .setGoal(null);

            bot.clearControlStates();

            bot.chat(
              "ایستادم."
            );

            return;
          }


          // JUMP

          if (command === "!jump") {

            bot.setControlState(
              "jump",
              true
            );

            setTimeout(() => {

              if (bot) {

                bot.setControlState(
                  "jump",
                  false
                );
              }

            }, 500);

            return;
          }


          // FIGHT

          if (command === "!fight") {

            const mob =
              bot.nearestEntity(
                entity =>
                  entity.type === "mob"
              );


            if (!mob) {

              bot.chat(
                "مابی نزدیکم نیست."
              );

              return;
            }


            bot.attack(mob);

            bot.chat(
              "دارم می‌جنگم!"
            );

            return;
          }


          // ASK AI

          if (
            command.startsWith(
              "!ask "
            )
          ) {

            const question =
              message.slice(5);


            const answer =
              await askAS32([

                {
                  role: "system",
                  content:
                    "You are AS 32 inside Minecraft. Answer briefly."
                },

                {
                  role: "user",
                  content: question
                }

              ]);


            bot.chat(
              answer
                .replace(/\n/g, " ")
                .slice(0, 220)
            );
          }
        }
      );


      bot.on("end", () => {

        bot = null;

      });


      bot.on(
        "error",
        error => {

          console.log(
            "Minecraft error:",
            error.message
          );
        }
      );


      res.json({
        message:
          "AS 32 داره وارد Minecraft میشه..."
      });

    } catch (error) {

      console.error(error);

      bot = null;

      res.status(500).json({
        error:
          "Minecraft connection error"
      });
    }
  }
);


// ======================================================
// ROBLOX COMPANION CODE
// ======================================================

app.get(
  "/api/roblox-code",
  (req, res) => {

res.type("text/plain").send(`

-- AS 32 ROBLOX COMPANION
-- Put this Script inside ServerScriptService
-- Create a model named AS32 in Workspace

local Players =
    game:GetService("Players")

local PathfindingService =
    game:GetService("PathfindingService")

local AS32 =
    workspace:WaitForChild("AS32")

local Humanoid =
    AS32:WaitForChild("Humanoid")

local Root =
    AS32:WaitForChild("HumanoidRootPart")


local function nearestPlayer()

    local chosen = nil
    local bestDistance = math.huge

    for _, player in ipairs(
        Players:GetPlayers()
    ) do

        local character =
            player.Character

        if character then

            local target =
                character:FindFirstChild(
                    "HumanoidRootPart"
                )

            if target then

                local distance =
                    (
                        target.Position
                        -
                        Root.Position
                    ).Magnitude

                if distance <
                   bestDistance
                then

                    bestDistance =
                        distance

                    chosen =
                        player
                end
            end
        end
    end

    return chosen
end


while true do

    task.wait(1.5)

    local player =
        nearestPlayer()

    if player and
       player.Character
    then

        local target =
            player.Character:
            FindFirstChild(
                "HumanoidRootPart"
            )

        if target then

            Humanoid:MoveTo(
                target.Position
            )

        end
    end
end

`);

});


// ======================================================
// WEBSITE
// ======================================================

app.get("/", (req, res) => {

res.send(`
<!DOCTYPE html>

<html lang="fa" dir="rtl">

<head>

<meta charset="UTF-8">

<meta
 name="viewport"
 content="width=device-width,initial-scale=1">

<title>AS 32</title>

<style>

*{
  box-sizing:border-box;
}

body{

  margin:0;

  min-height:100vh;

  font-family:
    Arial,sans-serif;

  color:white;

  background:
    radial-gradient(
      circle at top,
      #168cff,
      #092860 50%,
      #02091c
    );
}

main{

  width:min(850px,100%);

  min-height:100vh;

  margin:auto;

  padding:20px;

  display:flex;

  flex-direction:column;
}


/* TREE */

.tree{

  width:170px;

  height:150px;

  position:relative;

  margin:auto;
}


.trunk{

  position:absolute;

  bottom:0;

  left:70px;

  width:32px;

  height:100px;

  border-radius:
    50% 50% 10px 10px;

  background:
    linear-gradient(
      135deg,
      #249cff,
      #9e42ff
    );

  box-shadow:
    0 0 30px #664cff;
}


.branch{

  position:absolute;

  width:65px;

  height:13px;

  left:52px;

  top:67px;

  border-radius:20px;

  background:
    linear-gradient(
      90deg,
      #258cff,
      #a641ff
    );
}


.b1{
  transform:rotate(35deg);
}

.b2{
  transform:rotate(-35deg);
}


.leaf{

  position:absolute;

  width:34px;

  height:24px;

  border-radius:
    70% 20% 70% 20%;

  background:
    linear-gradient(
      135deg,
      #26a5ff,
      #b344ff
    );

  box-shadow:
    0 0 17px #7055ff;
}


.l1{
  top:10px;
  left:70px;
}

.l2{
  top:37px;
  left:24px;
}

.l3{
  top:34px;
  right:24px;
}

.l4{
  top:7px;
  left:40px;
}

.l5{
  top:8px;
  right:38px;
}


h1{

  text-align:center;

  font-size:42px;

  margin:5px;

  background:
    linear-gradient(
      90deg,
      #40b7ff,
      #bd5bff
    );

  color:transparent;

  background-clip:text;

  -webkit-background-clip:text;
}


.sub{

  text-align:center;

  opacity:.7;

  margin-bottom:15px;
}


.toolbar{

  display:flex;

  flex-wrap:wrap;

  gap:7px;

  margin-bottom:10px;
}


button{

  border:1px solid
    rgba(255,255,255,.2);

  color:white;

  background:
    rgba(20,40,110,.8);

  padding:9px 13px;

  border-radius:20px;

  cursor:pointer;
}


button.on{

  background:#8c2040;
}


#chat{

  flex:1;

  min-height:300px;

  overflow:auto;

  display:flex;

  flex-direction:column;

  gap:10px;

  padding:15px 0;
}


.msg{

  max-width:80%;

  padding:13px 15px;

  border-radius:18px;

  white-space:pre-wrap;

  line-height:1.6;
}


.me{

  align-self:flex-start;

  background:#1261da;
}


.as{

  align-self:flex-end;

  background:
    linear-gradient(
      135deg,
      #6a29b9,
      #25429e
    );
}


form{

  display:flex;

  gap:8px;

  padding:10px;

  border-radius:25px;

  background:
    rgba(5,18,60,.85);

  border:
    1px solid #7656e8;
}


textarea{

  flex:1;

  resize:none;

  border:0;

  outline:0;

  background:transparent;

  color:white;

  font-size:16px;

  padding:10px;
}


#send{

  width:50px;

  border-radius:50%;

  font-size:20px;

  background:
    linear-gradient(
      135deg,
      #1599ff,
      #9e44ff
    );
}


#preview{

  display:none;

  max-height:130px;

  max-width:200px;

  border-radius:12px;

  margin-bottom:8px;
}

</style>

</head>

<body>

<main>


<div class="tree">

<div class="trunk"></div>

<div class="branch b1"></div>

<div class="branch b2"></div>

<div class="leaf l1"></div>

<div class="leaf l2"></div>

<div class="leaf l3"></div>

<div class="leaf l4"></div>

<div class="leaf l5"></div>

</div>


<h1>AS 32</h1>

<div class="sub">
Artificial Intelligence
</div>


<div class="toolbar">

<button id="angry">
😠 Angry OFF
</button>

<button id="voice">
🔊 Voice ON
</button>

<button id="self">
🧠 Self Talk
</button>

<button id="photo">
🖼️ Photo
</button>

<button id="minecraft">
⛏️ Minecraft
</button>

<button id="roblox">
🎮 Roblox
</button>

</div>


<input
 id="file"
 type="file"
 accept="image/*"
 hidden
>

<img id="preview">


<div id="chat">

<div class="msg as">
سلام! من AS 32 هستم.
</div>

</div>


<form id="form">

<textarea
 id="input"
 placeholder="با AS 32 حرف بزن..."
 rows="1"
></textarea>

<button
 id="send"
 type="submit"
>
➤
</button>

</form>


</main>


<script>

const chat =
  document.getElementById(
    "chat"
  );

const form =
  document.getElementById(
    "form"
  );

const input =
  document.getElementById(
    "input"
  );

const angry =
  document.getElementById(
    "angry"
  );

const voice =
  document.getElementById(
    "voice"
  );

const self =
  document.getElementById(
    "self"
  );

const photo =
  document.getElementById(
    "photo"
  );

const file =
  document.getElementById(
    "file"
  );

const preview =
  document.getElementById(
    "preview"
  );

const minecraft =
  document.getElementById(
    "minecraft"
  );

const roblox =
  document.getElementById(
    "roblox"
  );


let angryMode = false;

let voiceMode = true;

let imageData = null;


let userId =
  localStorage.getItem(
    "as32-user"
  );


if (!userId) {

  userId =
    "u-" +
    Math.random()
      .toString(36)
      .slice(2);

  localStorage.setItem(
    "as32-user",
    userId
  );
}


function add(text,type){

  const div =
    document.createElement(
      "div"
    );

  div.className =
    "msg " + type;

  div.textContent =
    text;

  chat.appendChild(div);

  chat.scrollTop =
    chat.scrollHeight;

  return div;
}


function speak(text){

  if (!voiceMode)
    return;

  speechSynthesis.cancel();

  const s =
    new SpeechSynthesisUtterance(
      text
    );

  s.lang = "fa-IR";

  speechSynthesis.speak(s);
}


angry.onclick = () => {

  angryMode =
    !angryMode;

  angry.classList.toggle(
    "on",
    angryMode
  );

  angry.textContent =
    angryMode
      ? "😠 Angry ON"
      : "😠 Angry OFF";
};


voice.onclick = () => {

  voiceMode =
    !voiceMode;

  voice.textContent =
    voiceMode
      ? "🔊 Voice ON"
      : "🔇 Voice OFF";
};


photo.onclick = () => {

  file.click();

};


file.onchange = () => {

  const f =
    file.files[0];

  if (!f)
    return;

  const reader =
    new FileReader();

  reader.onload = () => {

    imageData =
      reader.result;

    preview.src =
      imageData;

    preview.style.display =
      "block";
  };

  reader.readAsDataURL(f);
};


async function send(
  message,
  selfTalk = false
){

  add(
    message ||
    "📷 تصویر",
    "me"
  );

  const thinking =
    add(
      "AS 32 در حال فکر کردن...",
      "as"
    );


  const response =
    await fetch(
      "/api/chat",
      {

        method:"POST",

        headers:{
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify({

            userId,

            message,

            angryMode,

            selfTalk,

            image:imageData
          })
      }
    );


  const data =
    await response.json();


  thinking.remove();


  const reply =
    data.reply ||
    data.error ||
    "خطا";


  add(
    reply,
    "as"
  );


  speak(reply);


  imageData = null;

  preview.style.display =
    "none";
}


form.onsubmit =
  async event => {

    event.preventDefault();

    const message =
      input.value.trim();

    if (
      !message &&
      !imageData
    ) return;


    input.value = "";


    await send(
      message,
      false
    );
};


self.onclick =
  async () => {

    await send(
      "یک Self Talk کوتاه با صدای بلند انجام بده.",
      true
    );
};


minecraft.onclick =
  async () => {

    const response =
      await fetch(
        "/api/minecraft/connect",
        {
          method:"POST"
        }
      );


    const data =
      await response.json();


    add(
      data.message ||
      data.error,
      "as"
    );
};


roblox.onclick =
  async () => {

    const response =
      await fetch(
        "/api/roblox-code"
      );


    const code =
      await response.text();


    await navigator.clipboard
      .writeText(code);


    add(
      "کد Roblox AS 32 کپی شد.",
      "as"
    );
};

</script>

</body>

</html>
`);

});


// ======================================================
// START
// ======================================================

app.listen(
  PORT,
  () => {

    console.log(
      "AS 32 ONLINE: " +
      PORT
    );
  }
);
