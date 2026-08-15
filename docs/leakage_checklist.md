# Temporal Leakage Checklist

A run is invalid if any answer below is "yes" without a documented offline-only justification.

- [ ] Was the retrieval index built using post-cutoff documents?
- [ ] Was IDF/vocabulary/statistical normalization fit on the full corpus?
- [ ] Were embeddings fine-tuned using post-cutoff labels/documents?
- [ ] Were post-cutoff citation counts exposed?
- [ ] Did prompt examples contain later discoveries?
- [ ] Were thresholds selected using hidden future labels?
- [ ] Did the agent call a live search engine without date restriction?
- [ ] Did a cache contain post-cutoff snippets?
- [ ] Did an external model retrieve current web knowledge?
- [ ] Did manual reviewers unintentionally edit prompts using future evidence?

## Recommended protection

For serious experiments, physically materialize:

```text
corpus_pre_T/
corpus_post_T/
```

and give the agent process access only to `corpus_pre_T/`.
