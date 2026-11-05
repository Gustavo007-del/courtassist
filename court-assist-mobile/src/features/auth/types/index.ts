export type ThemeMode = 'light' | 'dark' | 'system';
export type Language = 'en' | 'ml';
export type Preferences = {
  timezone: string; date_format: 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD';
  time_format: '12' | '24'; theme: ThemeMode;
  hearing_reminders: boolean; task_reminders: boolean; appointment_reminders: boolean;
  payment_reminders: boolean; daily_summary: boolean; updated_at: string;
};
export type Advocate = {
  id: string; full_name: string; email: string | null; phone_number: string | null;
  profile_image: string | null; signature_image: string | null;
  date_of_birth: string | null; gender: string | null; address: string | null;
  city: string | null; district: string | null; state: string | null; pin_code: string | null;
  enrollment_number: string | null; bar_council: string | null; enrollment_date: string | null;
  professional_designation: string | null; years_of_experience: number | null;
  office_name: string | null; office_address: string | null; office_phone: string | null;
  professional_email: string | null; areas_of_practice: string[];
  preferred_language: Language; preferences: Preferences | null;
  is_email_verified: boolean; is_phone_verified: boolean; created_at: string;
};
export type TokenResponse = { access_token: string; refresh_token: string; token_type: 'bearer'; access_expires_in: number; refresh_expires_in: number; user: Advocate };
