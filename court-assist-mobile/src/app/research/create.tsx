import { useLocalSearchParams } from 'expo-router';
import { ResearchItemForm } from '../../components/research/ResearchItemForm';
export default function Create() {
  const { caseId } = useLocalSearchParams<{ caseId?: string }>();
  return <ResearchItemForm caseId={caseId} />;
}
