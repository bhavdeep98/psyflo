import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Chip,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tabs,
  Tab,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow,
  CheckCircle,
  Error,
  TrendingUp,
  Assessment,
  Compare,
} from '@mui/icons-material';

interface EvaluationRun {
  run_id: string;
  status: 'running' | 'completed' | 'error';
  progress: number;
  current_step: string;
  started_at: string;
  completed_at?: string;
  config: {
    test_cases: number;
    model_name: string;
  };
  metrics?: {
    total_cases: number;
    completed_cases: number;
    overall_score: number;
    pass_rate: number;
  };
  results?: {
    model_name: string;
    total_cases: number;
    overall_score: number;
    pass_rate: number;
    metric_scores: {
      active_listening: number;
      empathy_validation: number;
      safety_trustworthiness: number;
      open_mindedness: number;
      clarity_encouragement: number;
      boundaries_ethical: number;
      holistic_approach: number;
    };
    timestamp: string;
    output_file: string;
  };
  error?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default function LLMEvaluation() {
  const [tabValue, setTabValue] = useState(0);
  const [testCases, setTestCases] = useState(50);
  const [modelName, setModelName] = useState('feelwell-baseline');
  const [apiKey, setApiKey] = useState('');
  const [currentRun, setCurrentRun] = useState<EvaluationRun | null>(null);
  const [completedRuns, setCompletedRuns] = useState<EvaluationRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll for progress when evaluation is running
  useEffect(() => {
    if (currentRun && currentRun.status === 'running') {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(
            `http://localhost:8000/api/llm/baseline-eval/${currentRun.run_id}`
          );
          const data = await response.json();
          setCurrentRun(data);

          if (data.status === 'completed') {
            setCompletedRuns((prev) => [data, ...prev]);
            clearInterval(interval);
          } else if (data.status === 'error') {
            setError(data.error);
            clearInterval(interval);
          }
        } catch (err) {
          console.error('Failed to fetch status:', err);
        }
      }, 2000); // Poll every 2 seconds

      return () => clearInterval(interval);
    }
  }, [currentRun]);

  const startEvaluation = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/llm/baseline-eval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          test_cases: testCases,
          model_name: modelName,
          api_key: apiKey || undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start evaluation');
      }

      const data = await response.json();
      
      // Fetch initial status
      const statusResponse = await fetch(
        `http://localhost:8000/api/llm/baseline-eval/${data.run_id}`
      );
      const statusData = await statusResponse.json();
      setCurrentRun(statusData);
      setTabValue(1); // Switch to progress tab
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getMetricColor = (score: number): string => {
    if (score >= 7.5) return '#4caf50'; // Green
    if (score >= 6.5) return '#ff9800'; // Orange
    return '#f44336'; // Red
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle sx={{ color: '#4caf50' }} />;
      case 'error':
        return <Error sx={{ color: '#f44336' }} />;
      default:
        return <CircularProgress size={20} />;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        🤖 LLM Evaluation Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Evaluate LLM responses against 7 clinical metrics from MentalChat16K research
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab label="Start Evaluation" icon={<PlayArrow />} iconPosition="start" />
          <Tab label="Current Run" icon={<Assessment />} iconPosition="start" />
          <Tab label="Results & Comparison" icon={<Compare />} iconPosition="start" />
        </Tabs>
      </Box>

      {/* Tab 1: Start Evaluation */}
      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Configuration
                </Typography>

                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Test Cases</InputLabel>
                  <Select
                    value={testCases}
                    onChange={(e) => setTestCases(Number(e.target.value))}
                    label="Test Cases"
                  >
                    <MenuItem value={50}>50 cases (~15 min, ~$2)</MenuItem>
                    <MenuItem value={100}>100 cases (~30 min, ~$4)</MenuItem>
                    <MenuItem value={200}>200 cases (~60 min, ~$7)</MenuItem>
                  </Select>
                </FormControl>

                <TextField
                  fullWidth
                  label="Model Name"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  label="OpenAI API Key (optional)"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  helperText="Leave empty if OPENAI_API_KEY env var is set"
                  sx={{ mb: 2 }}
                />

                <Button
                  variant="contained"
                  size="large"
                  fullWidth
                  startIcon={<PlayArrow />}
                  onClick={startEvaluation}
                  disabled={loading || (currentRun?.status === 'running')}
                >
                  {loading ? 'Starting...' : 'Start Evaluation'}
                </Button>

                {error && (
                  <Alert severity="error" sx={{ mt: 2 }}>
                    {error}
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  📊 Clinical Metrics
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Based on MentalChat16K (KDD 2025)
                </Typography>

                <Box sx={{ mt: 2 }}>
                  {[
                    { name: 'Active Listening', weight: 1.2 },
                    { name: 'Empathy & Validation', weight: 1.5 },
                    { name: 'Safety & Trustworthiness', weight: 2.0 },
                    { name: 'Open-mindedness', weight: 1.0 },
                    { name: 'Clarity & Encouragement', weight: 1.0 },
                    { name: 'Boundaries & Ethical', weight: 1.0 },
                    { name: 'Holistic Approach', weight: 1.0 },
                  ].map((metric) => (
                    <Box key={metric.name} sx={{ mb: 1 }}>
                      <Typography variant="body2">
                        {metric.name}
                        <Chip
                          label={`Weight: ${metric.weight}x`}
                          size="small"
                          sx={{ ml: 1, height: 20 }}
                        />
                      </Typography>
                    </Box>
                  ))}
                </Box>

                <Alert severity="info" sx={{ mt: 2 }}>
                  <strong>Target:</strong> Overall score ≥7.5/10, Pass rate ≥75%
                </Alert>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Tab 2: Current Run */}
      <TabPanel value={tabValue} index={1}>
        {currentRun ? (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    {getStatusIcon(currentRun.status)}
                    <Typography variant="h6" sx={{ ml: 1 }}>
                      {currentRun.config.model_name}
                    </Typography>
                    <Chip
                      label={currentRun.status}
                      color={
                        currentRun.status === 'completed'
                          ? 'success'
                          : currentRun.status === 'error'
                          ? 'error'
                          : 'primary'
                      }
                      sx={{ ml: 2 }}
                    />
                  </Box>

                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Run ID: {currentRun.run_id}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Started: {new Date(currentRun.started_at).toLocaleString()}
                  </Typography>

                  {currentRun.status === 'running' && (
                    <>
                      <Box sx={{ mt: 3, mb: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2">
                            {currentRun.current_step.replace(/_/g, ' ')}
                          </Typography>
                          <Typography variant="body2">
                            {(currentRun.progress * 100).toFixed(1)}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={currentRun.progress * 100}
                          sx={{ height: 10, borderRadius: 5 }}
                        />
                      </Box>

                      {currentRun.metrics && (
                        <Grid container spacing={2} sx={{ mt: 2 }}>
                          <Grid item xs={6} md={3}>
                            <Paper sx={{ p: 2, textAlign: 'center' }}>
                              <Typography variant="h4">
                                {currentRun.metrics.completed_cases}
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                / {currentRun.metrics.total_cases} cases
                              </Typography>
                            </Paper>
                          </Grid>
                          {currentRun.metrics.overall_score && (
                            <Grid item xs={6} md={3}>
                              <Paper sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="h4">
                                  {currentRun.metrics.overall_score.toFixed(2)}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  Current Score
                                </Typography>
                              </Paper>
                            </Grid>
                          )}
                        </Grid>
                      )}
                    </>
                  )}

                  {currentRun.status === 'completed' && currentRun.results && (
                    <Box sx={{ mt: 3 }}>
                      <Alert severity="success" sx={{ mb: 2 }}>
                        Evaluation completed successfully!
                      </Alert>

                      <Grid container spacing={2}>
                        <Grid item xs={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h4">
                              {currentRun.results.overall_score.toFixed(2)}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Overall Score
                            </Typography>
                          </Paper>
                        </Grid>
                        <Grid item xs={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h4">
                              {currentRun.results.pass_rate.toFixed(1)}%
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Pass Rate
                            </Typography>
                          </Paper>
                        </Grid>
                        <Grid item xs={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h4">
                              {currentRun.results.total_cases}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Test Cases
                            </Typography>
                          </Paper>
                        </Grid>
                        <Grid item xs={6} md={3}>
                          <Paper
                            sx={{
                              p: 2,
                              textAlign: 'center',
                              bgcolor:
                                currentRun.results.overall_score >= 7.5
                                  ? '#e8f5e9'
                                  : '#fff3e0',
                            }}
                          >
                            <Typography variant="h4">
                              {currentRun.results.overall_score >= 7.5 ? '✅' : '⚠️'}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {currentRun.results.overall_score >= 7.5
                                ? 'Meets Target'
                                : 'Below Target'}
                            </Typography>
                          </Paper>
                        </Grid>
                      </Grid>

                      <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
                        Metric Breakdown
                      </Typography>
                      <TableContainer component={Paper}>
                        <Table>
                          <TableHead>
                            <TableRow>
                              <TableCell>Metric</TableCell>
                              <TableCell align="right">Score</TableCell>
                              <TableCell align="right">Status</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {Object.entries(currentRun.results.metric_scores).map(
                              ([key, value]) => (
                                <TableRow key={key}>
                                  <TableCell>
                                    {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                                  </TableCell>
                                  <TableCell align="right">
                                    <Typography
                                      sx={{ color: getMetricColor(value), fontWeight: 'bold' }}
                                    >
                                      {value.toFixed(2)}/10
                                    </Typography>
                                  </TableCell>
                                  <TableCell align="right">
                                    <Chip
                                      label={value >= 7.5 ? 'Pass' : 'Below Target'}
                                      color={value >= 7.5 ? 'success' : 'warning'}
                                      size="small"
                                    />
                                  </TableCell>
                                </TableRow>
                              )
                            )}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Box>
                  )}

                  {currentRun.status === 'error' && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                      <strong>Error:</strong> {currentRun.error}
                    </Alert>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        ) : (
          <Alert severity="info">
            No evaluation running. Start one from the "Start Evaluation" tab.
          </Alert>
        )}
      </TabPanel>

      {/* Tab 3: Results & Comparison */}
      <TabPanel value={tabValue} index={2}>
        {completedRuns.length > 0 ? (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📈 Evaluation History
                  </Typography>
                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Model</TableCell>
                          <TableCell>Date</TableCell>
                          <TableCell align="right">Cases</TableCell>
                          <TableCell align="right">Overall Score</TableCell>
                          <TableCell align="right">Pass Rate</TableCell>
                          <TableCell align="right">Status</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {completedRuns.map((run) => (
                          <TableRow key={run.run_id}>
                            <TableCell>{run.config.model_name}</TableCell>
                            <TableCell>
                              {new Date(run.started_at).toLocaleDateString()}
                            </TableCell>
                            <TableCell align="right">{run.config.test_cases}</TableCell>
                            <TableCell align="right">
                              {run.results && (
                                <Typography
                                  sx={{
                                    color: getMetricColor(run.results.overall_score),
                                    fontWeight: 'bold',
                                  }}
                                >
                                  {run.results.overall_score.toFixed(2)}
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              {run.results && `${run.results.pass_rate.toFixed(1)}%`}
                            </TableCell>
                            <TableCell align="right">
                              <Chip
                                label={
                                  run.results && run.results.overall_score >= 7.5
                                    ? 'Meets Target'
                                    : 'Below Target'
                                }
                                color={
                                  run.results && run.results.overall_score >= 7.5
                                    ? 'success'
                                    : 'warning'
                                }
                                size="small"
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>

            {completedRuns.length >= 2 && (
              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      🔄 Model Comparison
                    </Typography>
                    <Alert severity="info">
                      Compare the latest two evaluations to see improvement
                    </Alert>
                    {/* Add comparison chart here */}
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        ) : (
          <Alert severity="info">
            No completed evaluations yet. Run an evaluation to see results here.
          </Alert>
        )}
      </TabPanel>
    </Box>
  );
}
