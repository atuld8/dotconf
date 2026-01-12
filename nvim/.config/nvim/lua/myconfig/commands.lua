vim.api.nvim_create_user_command("RunPipeline", function()
  require("myconfig.jira_pipeline").run(false)
end, {})

vim.api.nvim_create_user_command("RunPipelineAI", function()
  require("myconfig.jira_pipeline").run(true)
end, {})

