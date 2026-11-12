import axios from "axios";
import * as os from "os";
import { banUser } from "../utils/redis";
import { BlockedUserLog } from "../database/logDB/entities/BlockedUserLogEntities";
import { BanEventLog } from "../database/logDB/entities/BanEventLogEntities";
import { APILog } from "../database/logDB/services/addLog";
import { getLastCpuUsage } from "../utils/logger/createlog";

const BAN_DURATION_SECONDS = 600;

const getMemoryUsage = () => {
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  return ((totalMem - freeMem) / totalMem) * 100;
};

export const verifyUserActivity = async (info: APILog) => {
  try {
    if (!info.userPersona) {
      console.warn(
        `[BOT GUARD SKIPPED] Missing userPersona for request ${info.requestId}`
      );
      return;
    }

    const serviceType = process.env.SERVICE_TYPE || "MARKET";
    const payload = {
      requestId: info.requestId,
      apiTime: info.applicationTime + info.databaseTime,
      applicationTime: info.applicationTime,
      databaseTime: info.databaseTime,
      memoryUsage: getMemoryUsage(),
      serviceType: serviceType,
      cpuUsage: getLastCpuUsage(),
      endpointUrl: info.endpointUrl,
      apiMethod: info.apiMethod,
      userId: info.userId,
      userPersona: info.userPersona
    };

    const response = await axios.post(
      process.env.BOT_GUARD_URL + "/predict",
      payload
    );

    if (response.data.is_bot) {
      console.log(
        `[BOT DETECTED] Prediction: ${response.data.prediction}, ` +
        `UserID: ${info.userId || "UNKNOWN"}`
      );

      if (info.userId) {
        const banStartedAt = new Date();
        const banExpiresAt = new Date(
          banStartedAt.getTime() + BAN_DURATION_SECONDS * 1000
        );

        await banUser(info.userId, BAN_DURATION_SECONDS);

        try {
          const banEvent = new BanEventLog();
          banEvent.banStartedAt = banStartedAt;
          banEvent.banExpiresAt = banExpiresAt;
          banEvent.userId = info.userId;
          banEvent.userPersona = info.userPersona;
          banEvent.requestId = info.requestId;
          banEvent.banDurationSeconds = BAN_DURATION_SECONDS;
          await banEvent.save();

          const blockLog = new BlockedUserLog();
          blockLog.timestamp = banStartedAt;
          blockLog.userId = info.userId;
          blockLog.endpointUrl = info.endpointUrl;
          blockLog.apiMethod = info.apiMethod;
          blockLog.reason = `BOT DETECTED (prediction: ${response.data.prediction})`;
          blockLog.userAgent = "BotGuard/System";
          await blockLog.save();
        } catch (dbError) {
          console.error("Error saving ban event or block log:", dbError);
        }
      }
    }
  } catch (error: any) {
    console.error("Bot guard error:", error.message);
  }
};
