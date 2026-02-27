import { Context } from "grammy";
import type { Project } from "../db/schema.js";

export interface BotContext extends Context {
  project: Project;
}
