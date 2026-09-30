# เพื่อนคู่ใจ × LINE — คู่มือติดตั้ง

โปรเจกต์นี้มี 2 ส่วน:

```
liff-app/     หน้าเว็บแอป (LIFF) — สิ่งที่ผู้ใช้เห็นเมื่อเปิดแอป
line-bot/     เซิร์ฟเวอร์บอท (Messaging API) — ส่งลิงก์ให้เปิดแอป
```

เนื่องจากคุณมี Channel/Provider ของ LINE พร้อมอยู่แล้ว ให้ทำตามลำดับนี้ครับ

---

## ขั้นตอนที่ 1 — โฮสต์หน้าเว็บแอป (LIFF)

LIFF **ต้อง**ชี้ไปที่ URL ที่เป็น HTTPS จริงเท่านั้น (โฮสต์ในนี้ไม่ได้)
เลือกวิธีใดวิธีหนึ่ง เช่น:

- **Netlify / Vercel**: ลาก-วางโฟลเดอร์ `liff-app` ขึ้นไป (ฟรี, ได้ HTTPS ทันที)
- **GitHub Pages**
- เซิร์ฟเวอร์ของหน่วยงานคุณเอง

จดที่อยู่ที่ได้ เช่น `https://phuean-app.netlify.app`

---

## ขั้นตอนที่ 2 — สร้าง LIFF app ใน LINE Developers Console

1. เข้า https://developers.line.biz/console/ > เลือก Provider > เลือก Channel (Messaging API channel เดิมของคุณ)
2. ไปแท็บ **LIFF** > กด **Add**
3. กรอก:
   - LIFF app name: `เพื่อนคู่ใจ`
   - Size: `Full`
   - Endpoint URL: URL จากขั้นตอนที่ 1 (เช่น `https://phuean-app.netlify.app`)
   - Scope: เลือก `profile` (สำหรับดึงชื่อ/รูป) และ `openid`
4. กด Add แล้วคัดลอก **LIFF ID** ที่ได้ (รูปแบบ `1234567890-abcdEFGH`)

จากนั้นเปิดไฟล์ `liff-app/index.html` หาบรรทัด:
```js
const LIFF_ID = "YOUR_LIFF_ID";
```
แก้เป็น LIFF ID ที่คัดลอกมา แล้วอัปโหลดไฟล์ขึ้นโฮสต์อีกครั้ง

ทดสอบ: เปิดลิงก์ `https://liff.line.me/<LIFF_ID>` ผ่าน LINE บนมือถือ ควรเห็นหน้าแอปพร้อมชื่อคุณขึ้นทักทาย

---

## ขั้นตอนที่ 3 — ตั้งค่าบอท (Messaging API)

1. ในแชนแนลเดียวกัน ไปแท็บ **Messaging API**
2. คัดลอก **Channel secret** (อยู่แท็บ Basic settings) และออก **Channel access token** (long-lived) ในแท็บ Messaging API
3. ในเครื่อง/เซิร์ฟเวอร์ที่จะรันบอท:
   ```bash
   cd line-bot
   npm install
   cp .env.example .env
   ```
4. เปิดไฟล์ `.env` แล้วใส่ค่า:
   ```
   LINE_CHANNEL_ACCESS_TOKEN=<ที่คัดลอกมา>
   LINE_CHANNEL_SECRET=<ที่คัดลอกมา>
   LIFF_URL=https://liff.line.me/<LIFF_ID>
   ```
5. รันเซิร์ฟเวอร์:
   ```bash
   npm start
   ```
   (ระหว่างทดสอบในเครื่อง ใช้ `ngrok http 3000` เพื่อได้ URL สาธารณะชั่วคราว)

6. กลับไปที่ LINE Developers Console > แท็บ Messaging API > **Webhook URL** ใส่:
   ```
   https://<your-domain>/webhook
   ```
   แล้วกด **Verify** ให้ขึ้นสำเร็จ และเปิดสวิตช์ **Use webhook**

7. ปิด **Auto-reply messages** และ **Greeting messages** ในแท็บ Messaging API (เพื่อให้บอทของเราตอบเองแทน)

---

## ทดสอบทั้งระบบ

1. แอดบอทเป็นเพื่อนใน LINE ด้วย QR code หรือ LINE ID ที่อยู่ในแท็บ Messaging API
2. บอทควรทักทายพร้อมปุ่ม "💗 เปิดแอป เพื่อนคู่ใจ" ทันที (follow event)
3. พิมพ์อะไรก็ได้ในแชท บอทควรตอบปุ่มเปิดแอปกลับมาเสมอ
4. กดปุ่ม → แอปควรเปิดขึ้นในแอป LINE พร้อมชื่อของคุณที่หน้าแรก

---

## ปรับแต่งต่อได้

- เปลี่ยนข้อความ/ปุ่มในบอท: แก้ที่ `line-bot/server.js` ฟังก์ชัน `openAppButtonMessage`
- อยากให้กด "บันทึกอารมณ์" แล้วส่งข้อความกลับเข้าแชทจริง ๆ: ใน `liff-app/index.html` มีโค้ดตัวอย่างคอมเมนต์ไว้ในฟังก์ชัน `selectMood()` (ใช้ `liff.sendMessages`)
- อยากเก็บข้อมูลกิจกรรม/คะแนนแบบถาวร: ต้องต่อฐานข้อมูล (เช่น Firebase, Supabase) แทนการใช้ `alert()` — บอกมาได้เลยถ้าต้องการให้ช่วยต่อส่วนนี้ครับ
