"use server";

import fs from 'fs';
import path from 'path';

export async function getAdminConfig() {
  let adminEmail = process.env.ADMIN_EMAIL;
  let adminPassword = process.env.ADMIN_PASSWORD;

  try {
    const envPath = path.resolve(process.cwd(), '../.env');
    if (fs.existsSync(envPath)) {
      const envContent = fs.readFileSync(envPath, 'utf8');
      envContent.split('\n').forEach(line => {
        const trimmed = line.trim();
        if (trimmed.startsWith('ADMIN_EMAIL=')) {
          adminEmail = trimmed.substring('ADMIN_EMAIL='.length).trim();
        }
        if (trimmed.startsWith('ADMIN_PASSWORD=')) {
          adminPassword = trimmed.substring('ADMIN_PASSWORD='.length).trim();
        }
      });
    }
  } catch (error) {
    console.error("Error reading root .env", error);
  }

  return {
    adminEmail,
    adminPassword,
  };
}
