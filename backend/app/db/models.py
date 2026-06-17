# MongoDB collection schemas (for reference — Motor uses plain dicts, not Pydantic models)
#
# threads collection:
# {
#   _id: ObjectId,
#   github_comment_id: int,        // the original CodeSense inline comment ID
#   repo_full_name: str,           // "owner/repo"
#   pr_number: int,
#   file_path: str,
#   original_code_context: str,    // diff_hunk from the webhook payload
#   original_comment: str,         // what CodeSense said originally
#   turns: [
#     {
#       role: str,                 // "developer" | "codesense"
#       content: str,
#       github_comment_id: int,    // comment ID of this turn's reply
#       created_at: datetime
#     }
#   ],
#   created_at: datetime
# }
