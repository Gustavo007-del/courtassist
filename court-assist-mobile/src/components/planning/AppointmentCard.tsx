import { Pressable } from 'react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Card } from '../common/Card';
import type { Appointment } from '../../services/planning-api';
export function AppointmentCard({ item, onPress }: { item: Appointment; onPress: () => void }) { const { t } = useTranslation(); return <Pressable onPress={onPress}><Card><AppText style={{ fontWeight: '800' }}>{item.title}</AppText><AppText>{item.appointment_date} · {item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)}</AppText><AppText>{t(`planning.appointmentStatuses.${item.status}`)} · {t(`planning.appointmentTypes.${item.appointment_type}`, item.appointment_type)}</AppText></Card></Pressable>; }
