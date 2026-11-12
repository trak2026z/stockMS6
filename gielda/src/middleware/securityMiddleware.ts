import { Request, Response, NextFunction } from "express";
import { isUserBanned } from "../utils/redis";
import { AppError } from "../utils/appError";
import { BlockedUserLog } from "../database/logDB/entities/BlockedUserLogEntities";
import { RequestAttemptLog } from "../database/logDB/entities/RequestAttemptLogEntities";

const getSingleHeader = (value: string | string[] | undefined): string | undefined =>
  Array.isArray(value) ? value[0] : value;

const getUserPersona = (req: Request): string | undefined => {
  const bodyPersona = req.body?.userPersona;
  const headerPersona = getSingleHeader(req.headers["x-user-persona"]);
  const persona = bodyPersona || headerPersona;
  return typeof persona === "string" && persona.trim()
    ? persona.trim()
    : undefined;
};

const getRequestId = (req: Request): string | undefined => {
  const bodyRequestId = req.body?.requestId;
  const headerRequestId = getSingleHeader(req.headers["x-request-id"]);
  const requestId = bodyRequestId || headerRequestId;
  return typeof requestId === "string" && requestId.trim()
    ? requestId.trim()
    : undefined;
};

const saveRequestAttempt = async (
  req: Request,
  userId: number,
  userPersona: string,
  isBlocked: boolean
) => {
  const attempt = new RequestAttemptLog();
  attempt.timestamp = new Date();
  attempt.userId = userId;
  attempt.userPersona = userPersona;
  attempt.isBlocked = isBlocked;
  attempt.endpointUrl = req.originalUrl || req.url;
  attempt.apiMethod = req.method;
  attempt.requestId = getRequestId(req);
  await attempt.save();
};

export const securityMiddleware = async (
  req: Request,
  res: Response,
  next: NextFunction
) => {
  const userIdParam = req.body?.userId || req.params.id || req.headers["x-user-id"];

  if (!userIdParam) {
    return next();
  }

  const userId = Number(Array.isArray(userIdParam) ? userIdParam[0] : userIdParam);
  if (Number.isNaN(userId)) {
    return next();
  }

  const userPersona = getUserPersona(req);
  if (!userPersona) {
    console.warn(
      `[REQUEST ATTEMPT NOT LOGGED] Missing userPersona for user ${userId}`
    );
    return next();
  }

  try {
    const banned = await isUserBanned(userId);

    // Log every attributable attempt, not only rejected requests. This is
    // required for the denominators of BRSR and HRR.
    await saveRequestAttempt(req, userId, userPersona, banned);

    if (banned) {
      console.log(`[BLOCKED] Request from banned user: ${userId}`);

      try {
        const log = new BlockedUserLog();
        log.timestamp = new Date();
        log.userId = userId;
        log.endpointUrl = req.originalUrl || req.url;
        log.apiMethod = req.method;
        log.reason = "User banned in Redis";
        log.userAgent = req.get("User-Agent") || "Unknown";
        await log.save();
      } catch (error) {
        console.error("Error saving legacy blocked-user log:", error);
      }

      return next(new AppError("Access Denied", 403));
    }
  } catch (error) {
    // Logging failure must not silently bypass an actual Redis ban check.
    console.error("Security middleware error:", error);
    return next(error);
  }

  return next();
};
