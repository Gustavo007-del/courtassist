module.exports = ({ config }) => {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL || '';
  const allowHttp = process.env.COURT_ASSIST_ALLOW_HTTP_DEV === '1' && apiUrl.startsWith('http://');
  return {
    ...config,
    plugins: config.plugins.map((plugin) => plugin === 'expo-build-properties'
      ? ['expo-build-properties', { android: { usesCleartextTraffic: allowHttp } }]
      : plugin),
  };
};
